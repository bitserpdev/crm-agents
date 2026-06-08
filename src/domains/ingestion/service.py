from typing import Optional

from core.qdrant import get_embedder, get_qdrant
from .repository import repo
from .model import RawEventList, SemanticSearchResult, SemanticHit, PlatformStat


class IngestionService:

    def get_raw_events(
        self,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> RawEventList:
        records = repo.list_raw_events(platform, status, limit, offset)
        return RawEventList(total=len(records), records=records)

    def get_stats(self) -> list[PlatformStat]:
        rows = repo.get_stats()
        return [PlatformStat(**r) for r in rows]

    def semantic_search(
        self,
        q: str,
        limit: int = 10,
        platform: Optional[str] = None,
    ) -> SemanticSearchResult:
        try:
            vector = get_embedder().embed_query(q)
            client = get_qdrant()

            qf = None
            if platform:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                qf = Filter(must=[
                    FieldCondition(
                        key="source_platform",
                        match=MatchValue(value=platform),
                    )
                ])

            results = client.query_points(
                collection_name="lz_raw_message_embeddings",
                query=vector,
                limit=limit,
                query_filter=qf,
            )
            hits = results.points if hasattr(results, "points") else list(results)

            return SemanticSearchResult(
                query=q,
                results=[
                    SemanticHit(
                        event_id=h.payload.get("point_id"),
                        score=round(h.score, 4),
                        source_platform=h.payload.get("source_platform"),
                        received_at=h.payload.get("received_at"),
                        dedup_key=h.payload.get("dedup_key"),
                    )
                    for h in hits
                ],
            )

        except Exception as e:
            return SemanticSearchResult(query=q, results=[], error=str(e))


service = IngestionService()