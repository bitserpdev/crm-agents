from typing import Dict, List , Any

_FIELD_ALIASES: Dict[str, List[str]] = {
    "email":           ["email", "e-mail"],
    "first_name":      ["first_name", "firstname", "first name", "fname"],
    "last_name":       ["last_name", "lastname", "last name", "lname"],
    "phone":           ["phone", "phone_number", "phonenumber", "mobile"],
    "company":         ["company", "company_name", "company name", "organization"],
    "job_title":       ["job_title", "jobtitle", "title", "position"],
    "city":            ["city"],
    "country":         ["country"],
    "linkedin_url":    ["linkedin_url", "linkedin", "linkedin url"],
    "lifecycle_stage": ["lifecycle_stage", "stage"],
    "contact_type":    ["contact_type", "type"],
    "lead_score":      ["lead_score"],
    "intent_score":    ["intent_score"],
    "overall_score":   ["overall_score"],
    "tags":            ["tags", "tag"],
}


_CONTACT_DEFAULTS: Dict[str, Any] = {
    "contact_type":    "prospect",
    "lifecycle_stage": "subscriber",
    "source_platform": "csv-upload",
    "intent_score":    0.5,
    "lead_score":      50,
}
 
_CSV_ENCODINGS = ("utf-8-sig", "utf-8", "latin-1")