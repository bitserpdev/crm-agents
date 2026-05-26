import os
import redis
from agent2.state import Agent2State
from langchain_ollama import OllamaEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

r        = redis.from_url(os.getenv("REDIS_URL"))
qdrant   = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
embedder = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
)

def embed_node(state: Agent2State) -> Agent2State:
    profiles = [r for r in state["loaded_records"]
                if r.get("record_type") == "profile"]

    if not profiles:
        print("[agent2/embed] No profiles to embed")
        state["run_status"] = "done"
        return state

    print(f"[agent2/embed] Embedding {len(profiles)} contact profiles...")

    for record in profiles:
        try:
            contact_id = record.get("_contact_id")
            if not contact_id:
                continue

            # Build text for embedding
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

            vector = embedder.embed_query(text)

            # op_contact_profiles
            qdrant.upsert(
                collection_name="op_contact_profiles",
                points=[PointStruct(
                    id=contact_id,
                    vector=vector,
                    payload={
                        "point_id":        contact_id,
                        "company_id":      record.get("_company_id", ""),
                        "lifecycle_stage": record.get("lifecycle_stage", "subscriber"),
                        "contact_type":    record.get("contact_type", "prospect"),
                        "overall_score":   record.get("lead_score", 0),
                        "updated_at":      record.get("_received_at", ""),
                    }
                )]
            )

            # op_icp_profiles
            qdrant.upsert(
                collection_name="op_icp_profiles",
                points=[PointStruct(
                    id=contact_id,
                    vector=vector,
                    payload={
                        "point_id":   contact_id,
                        "segment_id": "",
                        "industry":   record.get("company_name", ""),
                        "fit_score":  record.get("lead_score", 0),
                        "updated_at": record.get("_received_at", ""),
                    }
                )]
            )

            # Push to op:lead_score_queue for Agent 5 rescoring
            intent = float(record.get("intent_score", 0.5))
            r.zadd("op:lead_score_queue",
                   {record.get("_event_id", contact_id): intent})

            print(f"[agent2/embed] ✓ Embedded contact: {contact_id[:16]}...")

        except Exception as e:
            print(f"[agent2/embed] Embed error: {e}")
            state["errors"].append(f"Embed error: {str(e)}")

    state["run_status"] = "done"
    return state
