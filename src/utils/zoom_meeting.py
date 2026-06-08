import os
import time
import requests

_cached_zoom_token: str | None = None
_zoom_token_expiry: float = 0


def _get_zoom_access_token() -> str:
    global _cached_zoom_token, _zoom_token_expiry

    if _cached_zoom_token and time.time() < _zoom_token_expiry:
        return _cached_zoom_token

    resp = requests.post(
        "https://zoom.us/oauth/token",
        params={
            "grant_type": "account_credentials",
            "account_id": os.getenv("ZOOM_ACCOUNT_ID"),
        },
        auth=(os.getenv("ZOOM_CLIENT_ID"), os.getenv("ZOOM_CLIENT_SECRET")),
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    _cached_zoom_token = data["access_token"]
    _zoom_token_expiry = time.time() + data["expires_in"] - 300

    return _cached_zoom_token


def create_zoom_meeting(
    title: str,
    start_time: str,  # ISO string e.g. "2025-01-20T10:00:00Z"
    duration_minutes: int = 60,
    timezone: str = "UTC",
    host_video: bool = True,
    participant_video: bool = True,
    join_before_host: bool = True,
    waiting_room: bool = False,
) -> dict:
    """
    Creates a scheduled Zoom meeting.

    Returns:
        {
            "join_url":   str,
            "meeting_id": str,
            "start_time": str,
            "duration":   int,
            "topic":      str,
        }
    """
    token = _get_zoom_access_token()

    resp = requests.post(
        "https://api.zoom.us/v2/users/me/meetings",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "topic": title,
            "type": 2,
            "start_time": start_time,
            "duration": duration_minutes,
            "timezone": timezone,
            "settings": {
                "host_video": host_video,
                "participant_video": participant_video,
                "join_before_host": join_before_host,
                "waiting_room": waiting_room,
            },
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    return {
        "join_url": data["join_url"],
        "meeting_id": str(data["id"]),
        "start_time": data["start_time"],
        "duration": data["duration"],
        "topic": data["topic"],
    }
