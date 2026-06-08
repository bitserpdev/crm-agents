from agents.agent2.state import Agent2State
from core.qdrant import get_qdrant, get_embedder
from core.redis import get_redis
from core.logger import logger


def embed_node(state: Agent2State) -> Agent2State:
    profiles = [r for r in state["loaded_records"]
                if r.get("record_type") == "profile"]

    if not profiles:
        logger.info("[agent2/embed] No profiles to embed")
        state["run_status"] = "done"
        return state

    r        = get_redis()
    qdrant   = get_qdrant()
    embedder = get_embedder()

    logger.info("[agent2/embed] Embedding profiles", count=len(profiles))

    for record in profiles:
        try:
            contact_id = record.get("_contact_id")
            if not contact_id:
                continue

            text = " ".join(filter(None, [
                record.get("first_name", ""),
                record.get("last_name", ""),
                record.get("job_title", ""),
                record.get("company_name", ""),
                record.get("summary", ""),
                " ".join(record.get("tags", [])),
            ]))
            if not text.strip():
                continue

            from qdrant_client.models import PointStruct
            vector = embedder.embed_query(text)

            qdrant.upsert(
                collection_name="op_contact_profiles",
                points=[PointStruct(
                    id=contact_id,
                    vector=vector,
                    payload={
                        "point_id":       contact_id,
                        "company_id":     record.get("_company_id", ""),
                        "lifecycle_stage": record.get("lifecycle_stage", "subscriber"),
                        "contact_type":   record.get("contact_type", "prospect"),
                        "overall_score":  record.get("lead_score", 0),
                        "updated_at":     record.get("_received_at", ""),
                    },
                )],
            )

            qdrant.upsert(
                collection_name="op_icp_profiles",
                points=[PointStruct(
                    id=contact_id,
                    vector=vector,
                    payload={
                        "point_id":  contact_id,
                        "segment_id": "",
                        "industry":  record.get("company_name", ""),
                        "fit_score": record.get("lead_score", 0),
                        "updated_at": record.get("_received_at", ""),
                    },
                )],
            )

            r.zadd("op:lead_score_queue", {
                record.get("_event_id", contact_id): float(record.get("intent_score", 0.5))
            })
            logger.info("[agent2/embed] Embedded", contact_id=contact_id[:16])

        except Exception as e:
            logger.error("[agent2/embed] Embed error", error=str(e))
            state["errors"].append(f"Embed error: {str(e)}")

    state["run_status"] = "done"
    return state