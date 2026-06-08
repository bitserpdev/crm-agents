from typing import Optional

from .repository import repo
from .model import LeadList


class CrmService:

    def get_leads(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> LeadList:
        records = repo.list_leads(search, status, limit, offset)
        return LeadList(records=records)

service = CrmService()