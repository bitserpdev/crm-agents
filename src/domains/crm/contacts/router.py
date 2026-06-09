from typing import Optional
from fastapi import APIRouter, Query
from fastapi import UploadFile, File, Form, HTTPException
from .model import ContactList, ContactDetail
from .service import service
from core.logger import logger

router = APIRouter()


@router.post("/upload-csv")
async def upload_contacts_csv(
    file: UploadFile = File(...),
):
    """
    Upload CSV file with contacts

    Expected CSV columns:
    - email (required)
    - first_name
    - last_name
    - phone
    - company
    - job_title
    - city
    - country
    - tags (comma-separated)
    - linkedin_url
    """

    # Validate file type
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    try:
        # Read file content
        contents = await file.read()

        # Process upload
        results = service.upload_contacts(contents)

        return {
            "success": True,
            "message": f"Successfully processed {results['success']} out of {results['total']} contacts",
            "data": results,
        }

    except HTTPException as e:
        raise

    except Exception as e:
        logger.error(f"CSV upload failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to upload contacts: {str(e)}"
        )


@router.get("", response_model=ContactList)
def get_contacts(
    search: Optional[str] = None,
    stage: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    return service.get_contacts(search, stage, limit, offset)


@router.get("/{contact_id}", response_model=ContactDetail)
def get_contact_detail(contact_id: str):
    return service.get_contact(contact_id)
