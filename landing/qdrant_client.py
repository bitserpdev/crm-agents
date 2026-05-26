import os
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
from langchain_ollama import OllamaEmbeddings

QDRANT_URL  = os.getenv("QDRANT_URL", "http://localhost:6333")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_URL  = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

SEMANTIC_DEDUP_THRESHOLD = 0.92
IDENTITY_MATCH_THRESHOLD = 0.88
INTENT_THRESHOLD         = 0.7

_qdrant   = None
_embedder = None

def get_qdrant():
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(url=QDRANT_URL)
    return _qdrant

def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = OllamaEmbeddings(
            model=EMBED_MODEL,
            base_url=OLLAMA_URL
        )
    return _embedder

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
            score_threshold=threshold
        )
        return results.points if hasattr(results, 'points') else results
    except AttributeError:
        try:
            # Fall back to older API
            return client.search(
                collection_name=collection,
                query_vector=vector,
                limit=limit,
                score_threshold=threshold
            )
        except Exception as e:
            print(f"[qdrant] Search error: {e}")
            return []

def embed_and_store(record: dict, event_id: str):
    text = _build_text(record)
    if not text:
        print("[qdrant] Empty text — skipping embedding")
        return

    vector = get_embedder().embed_query(text)
    client = get_qdrant()

    # 1. Semantic dedup check
    hits = _search("lz_raw_message_embeddings", vector, SEMANTIC_DEDUP_THRESHOLD)
    if hits:
        print(f"[qdrant] Semantic duplicate found — skipping")
        return

    payload = {
        "point_id":        event_id,
        "dedup_key":       record.get("dedup_key", ""),
        "source_platform": record.get("platform", "linkedin"),
        "received_at":     record.get("received_at", ""),
    }

    # 2. Store in raw message embeddings
    client.upsert(
        collection_name="lz_raw_message_embeddings",
        points=[PointStruct(id=event_id, vector=vector, payload=payload)]
    )
    print(f"[qdrant] Stored in lz_raw_message_embeddings")

    # 3. Contact fingerprint
    id_hits = _search("lz_contact_fingerprints", vector, IDENTITY_MATCH_THRESHOLD)
    if id_hits:
        print(f"[qdrant] Fuzzy identity match found")
    else:
        client.upsert(
            collection_name="lz_contact_fingerprints",
            points=[PointStruct(
                id=event_id,
                vector=vector,
                payload={
                    "point_id": event_id,
                    "event_id": event_id,
                    "dedup_key": record.get("dedup_key", "")
                }
            )]
        )
        print(f"[qdrant] Stored in lz_contact_fingerprints")

    # 4. Intent signal
    intent_score = float(record.get("intent_score", 0.5))
    if intent_score >= INTENT_THRESHOLD:
        client.upsert(
            collection_name="lz_early_intent_signals",
            points=[PointStruct(
                id=event_id,
                vector=vector,
                payload={
                    "point_id":     event_id,
                    "event_id":     event_id,
                    "intent_score": intent_score,
                    "received_at":  record.get("received_at", ""),
                }
            )]
        )
        print(f"[qdrant] High intent signal stored (score={intent_score})")

    print(f"[qdrant] ✓ All embeddings stored for event {event_id}")
