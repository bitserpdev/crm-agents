# src/domains/zoom/router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import os

router = APIRouter()


class CreateMeetingRequest(BaseModel):
    title: str
    start_time: str  # ISO format: "2026-06-09T15:30:00Z"
    duration_minutes: int = 30
    timezone: str = "UTC"
    host_video: bool = True
    participant_video: bool = True
    join_before_host: bool = True
    waiting_room: bool = False


class CreateMeetingResponse(BaseModel):
    success: bool
    join_url: Optional[str] = None
    meeting_id: Optional[str] = None
    start_time: Optional[str] = None
    duration: Optional[int] = None
    topic: Optional[str] = None
    error: Optional[str] = None


@router.post("/create-meeting", response_model=CreateMeetingResponse)
def create_meeting(request: CreateMeetingRequest):
    """Create a Zoom meeting"""
    try:
        from utils.zoom_meeting import create_zoom_meeting

        result = create_zoom_meeting(
            title=request.title,
            start_time=request.start_time,
            duration_minutes=request.duration_minutes,
            timezone=request.timezone,
            host_video=request.host_video,
            participant_video=request.participant_video,
            join_before_host=request.join_before_host,
            waiting_room=request.waiting_room,
        )

        return CreateMeetingResponse(
            success=True,
            join_url=result["join_url"],
            meeting_id=result["meeting_id"],
            start_time=result["start_time"],
            duration=result["duration"],
            topic=result["topic"],
        )

    except Exception as e:
        return CreateMeetingResponse(success=False, error=str(e))


@router.get("/test")
def test_zoom():
    """Test Zoom API connection"""
    try:
        from utils.zoom_meeting import _get_zoom_access_token

        token = _get_zoom_access_token()
        return {
            "success": True,
            "message": "Zoom API connected successfully",
            "token_preview": token[:20] + "...",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/create-test-meeting")
def create_test_meeting():
    """Create a test meeting for right now"""
    from datetime import datetime, timedelta

    # Set meeting for 30 minutes from now
    start_time = (datetime.utcnow() + timedelta(minutes=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    try:
        from utils.zoom_meeting import create_zoom_meeting

        result = create_zoom_meeting(
            title="Test Meeting - BITS CRM",
            start_time=start_time,
            duration_minutes=30,
            timezone="UTC",
        )

        return {"success": True, "meeting": result}

    except Exception as e:
        return {"success": False, "error": str(e)}
