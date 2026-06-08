from typing import Optional
from fastapi import HTTPException

from .repository import repo
from .model import ContactList, ContactDetail


class CrmService:

    def get_contacts(
        self,
        search: Optional[str] = None,
        stage: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ContactList:
        total, records = repo.list_contacts(search, stage, limit, offset)
        return ContactList(total=total, records=records)

    def get_contact(self, contact_id: str) -> ContactDetail:
        row = repo.get_contact_by_id(contact_id)
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")
        return ContactDetail(**row)

service = CrmService()