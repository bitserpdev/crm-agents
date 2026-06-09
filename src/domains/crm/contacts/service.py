import io
import csv
import re
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core.logger import logger
from .model import ContactDetail, ContactList
from .repository import repo
from constant.contacts import _FIELD_ALIASES, _CONTACT_DEFAULTS, _CSV_ENCODINGS


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

    def upload_contacts(self, csv_content: bytes) -> Dict[str, Any]:
        """Parse a CSV upload and bulk-insert contacts into the CRM."""
        try:
            contacts = self._parse_csv(csv_content)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        for contact in contacts:
            contact["created_by_agent"] = "csv-upload"

        return repo.bulk_add_contacts(contacts)

    # ------------------------------------------------------------------
    # CSV parsing (private)
    # ------------------------------------------------------------------

    def _decode_csv(self, raw: bytes) -> str:
        for encoding in _CSV_ENCODINGS:
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("Could not decode CSV file — unsupported encoding.")

    @staticmethod
    def _normalise_header(h: str) -> str:
        """
        Extract canonical field name from a CSV header.

        Handles two formats:
          - Plain CSV:       'email'                         → 'email'
          - Excel export:    'First Name\n[first_name]\n...' → 'first_name'
        """
        match = re.search(r"\[([^\]]+)\]", h)
        if match:
            return match.group(1).lower()
        return h.strip().strip("\ufeff").lower()

    def _build_header_map(self, fieldnames: List[str]) -> Dict[str, str]:
        """Return {canonical_field: actual_csv_header} for each recognised column."""
        # Map normalised header → original header string
        normalised = {self._normalise_header(h): h for h in fieldnames}

        header_map: Dict[str, str] = {}
        for field, aliases in _FIELD_ALIASES.items():
            # First: direct match on normalised header (covers Excel export)
            if field in normalised:
                header_map[field] = normalised[field]
                continue
            # Then: alias list match (covers plain CSV variants)
            for alias in aliases:
                if alias.lower() in normalised:
                    header_map[field] = normalised[alias.lower()]
                    break

        return header_map

    def _parse_row(
        self,
        row: Dict[str, str],
        header_map: Dict[str, str],
        row_num: int,
    ) -> Dict[str, Any]:
        contact: Dict[str, Any] = {}

        for field, csv_header in header_map.items():
            value = row.get(csv_header, "").strip()
            if value:
                contact[field] = value

        # Normalise numeric score fields
        for score_field, cast in (
            ("lead_score", int),
            ("intent_score", float),
            ("overall_score", int),
        ):
            if score_field in contact:
                try:
                    contact[score_field] = cast(contact[score_field])
                except ValueError:
                    raise ValueError(
                        f"Row {row_num}: '{score_field}' must be a number, "
                        f"got '{contact[score_field]}'."
                    )

        # Normalise tags → list[str]
        if "tags" in contact:
            contact["tags"] = [
                t.strip() for t in contact["tags"].split(",") if t.strip()
            ]

        # Apply defaults for missing fields
        for key, default in _CONTACT_DEFAULTS.items():
            contact.setdefault(key, default)

        return contact

    def _parse_csv(self, csv_content: bytes) -> List[Dict[str, Any]]:
        csv_text = self._decode_csv(csv_content)
        reader = csv.DictReader(io.StringIO(csv_text))

        if not reader.fieldnames:
            raise ValueError("CSV file has no headers.")

        header_map = self._build_header_map(list(reader.fieldnames))

        if "email" not in header_map:
            raise ValueError("CSV must contain an 'email' column.")

        contacts: List[Dict[str, Any]] = []
        for row_num, row in enumerate(reader, start=2):
            contact = self._parse_row(row, header_map, row_num)
            contacts.append(contact)

        logger.info("csv_parsed", extra={"total_rows": len(contacts)})
        return contacts


service = CrmService()