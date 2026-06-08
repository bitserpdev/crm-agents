import os
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from langchain_ollama import OllamaEmbeddings
from core.logger import logger

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

SEMANTIC_DEDUP_THRESHOLD = 0.92
IDENTITY_MATCH_THRESHOLD = 0.88
INTENT_THRESHOLD = 0.7
BATCH_SIZE = int(os.getenv("QDRANT_BATCH_SIZE", 64))

_qdrant = None
_embedder = None


def get_qdrant():
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(url=QDRANT_URL)
        logger.info(f"[qdrant] Client initialized → {QDRANT_URL}")
    return _qdrant


def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_URL)
        logger.info(f"[qdrant] Embedder initialized (model={EMBED_MODEL})")
    return _embedder


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_text(record: dict) -> str:
    parts = [
        record.get("title", ""),
        record.get("clean_title", ""),
        record.get("name", ""),
        record.get("headline", ""),
        record.get("description", ""),
        record.get("summary", ""),
        record.get("company", ""),
        record.get("email", ""),
    ]
    return " ".join(p for p in parts if p).strip()


def _search(collection: str, vector: list, threshold: float, limit: int = 1):
    """Compatible search wrapper for newer qdrant-client versions."""
    client = get_qdrant()
    try:
        # Try newer API first (qdrant-client >= 1.7)
        results = client.query_points(
            collection_name=collection,
            query=vector,
            limit=limit,
            score_threshold=threshold,
        )
        return results.points if hasattr(results, "points") else results
    except AttributeError:
        try:
            # Fall back to older API
            return client.search(
                collection_name=collection,
                query_vector=vector,
                limit=limit,
                score_threshold=threshold,
            )
        except Exception as e:
            logger.error(f"[qdrant] Search error in '{collection}': {e}")
            return []


def _safe_point_id(event_id: str) -> str | int:
    """Qdrant point IDs must be UUID or unsigned int."""
    try:
        uuid.UUID(str(event_id))
        return str(event_id)
    except ValueError:
        # Hash to a stable positive int if not a UUID
        return abs(hash(event_id)) % (2**63)


# ── Single record ─────────────────────────────────────────────────────────────


def embed_and_store(record: dict, event_id: str):
    text = _build_text(record)
    if not text:
        logger.warning(f"[qdrant] Empty text for event {event_id} — skipping")
        return

    vector = get_embedder().embed_query(text)
    point_id = _safe_point_id(event_id)
    client = get_qdrant()

    # 1. Semantic dedup check
    if _search("lz_raw_message_embeddings", vector, SEMANTIC_DEDUP_THRESHOLD):
        logger.info(f"[qdrant] Semantic duplicate — skipping {event_id}")
        return

    base_payload = {
        "point_id": event_id,
        "dedup_key": record.get("dedup_key", ""),
        "source_platform": record.get("platform", "linkedin"),
        "received_at": record.get("received_at", ""),
    }

    # 2. Store in raw message embeddings
    client.upsert(
        collection_name="lz_raw_message_embeddings",
        points=[PointStruct(id=point_id, vector=vector, payload=base_payload)],
    )

    # 3. Contact fingerprint
    if not _search("lz_contact_fingerprints", vector, IDENTITY_MATCH_THRESHOLD):
        client.upsert(
            collection_name="lz_contact_fingerprints",
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "point_id": event_id,
                        "event_id": event_id,
                        "dedup_key": record.get("dedup_key", ""),
                    },
                )
            ],
        )

    # 4. Intent signal
    intent_score = float(record.get("intent_score", 0.5))
    if intent_score >= INTENT_THRESHOLD:
        client.upsert(
            collection_name="lz_early_intent_signals",
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "point_id": event_id,
                        "event_id": event_id,
                        "intent_score": intent_score,
                        "received_at": record.get("received_at", ""),
                    },
                )
            ],
        )
        logger.info(f"[qdrant] High intent stored (score={intent_score})")

    logger.info(f"[qdrant] ✓ Stored event {event_id}")


# ── Batch (scalable path) ─────────────────────────────────────────────────────


def embed_and_store_batch(records: list[dict], event_ids: list[str]):
    """
    Embeds and stores multiple records in one shot.
    Uses embed_documents() for a single batched Ollama call
    and bulk upsert per collection.
    """
    if len(records) != len(event_ids):
        raise ValueError("records and event_ids must have the same length")

    texts = [_build_text(r) for r in records]

    # Filter empties
    valid = [(t, r, eid) for t, r, eid in zip(texts, records, event_ids) if t]
    if not valid:
        logger.warning("[qdrant] No valid texts in batch — skipping")
        return

    texts_valid, records_valid, ids_valid = zip(*valid)

    # Single batched embedding call
    logger.info(f"[qdrant] Embedding batch of {len(texts_valid)} records...")
    vectors = get_embedder().embed_documents(list(texts_valid))

    raw_points = []
    fingerprint_points = []
    intent_points = []
    client = get_qdrant()

    for vector, record, event_id in zip(vectors, records_valid, ids_valid):
        point_id = _safe_point_id(event_id)

        # Dedup check per record (still needed)
        if _search("lz_raw_message_embeddings", vector, SEMANTIC_DEDUP_THRESHOLD):
            logger.debug(f"[qdrant] Duplicate skipped: {event_id}")
            continue

        raw_points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "point_id": event_id,
                    "dedup_key": record.get("dedup_key", ""),
                    "source_platform": record.get("platform", "linkedin"),
                    "received_at": record.get("received_at", ""),
                },
            )
        )

        if not _search("lz_contact_fingerprints", vector, IDENTITY_MATCH_THRESHOLD):
            fingerprint_points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "point_id": event_id,
                        "event_id": event_id,
                        "dedup_key": record.get("dedup_key", ""),
                    },
                )
            )

        intent_score = float(record.get("intent_score", 0.5))
        if intent_score >= INTENT_THRESHOLD:
            intent_points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "point_id": event_id,
                        "event_id": event_id,
                        "intent_score": intent_score,
                        "received_at": record.get("received_at", ""),
                    },
                )
            )

    # Bulk upserts — one network round-trip per collection
    def _bulk_upsert(collection: str, points: list):
        for i in range(0, len(points), BATCH_SIZE):
            client.upsert(collection_name=collection, points=points[i : i + BATCH_SIZE])

    if raw_points:
        _bulk_upsert("lz_raw_message_embeddings", raw_points)
    if fingerprint_points:
        _bulk_upsert("lz_contact_fingerprints", fingerprint_points)
    if intent_points:
        _bulk_upsert("lz_early_intent_signals", intent_points)

    logger.info(
        f"[qdrant] ✓ Batch complete — {len(raw_points)} stored, "
        f"{len(records_valid) - len(raw_points)} deduplicated"
    )
