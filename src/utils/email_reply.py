import re
from typing import Optional

_DAYS = (
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday",
)

_DETAIL_PHRASES = (
    "share additional details", "share more", "more information", "more details",
    "learn more about", "specific services", "how your solutions", "how your team",
    "could you please share", "tell me more", "additional information",
    "your approach", "services you offer", "explore potential",
)

_FULL_WEEKDAYS = (
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday",
)
_SHORT_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_WEEKDAY_RE = re.compile(
    r"\b(?:"
    + "|".join(_FULL_WEEKDAYS + _SHORT_WEEKDAYS)
    + r")\b",
    re.I,
)
_TZ_RE = re.compile(r"\b(?:pkt|est|utc|gmt|pst|cet|edt|pdt)\b", re.I)
_MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)
_SCHEDULE_PHRASES = (
    "schedule a call", "schedule a meeting", "book a call", "book a meeting",
    "set up a call", "arrange a call", "arrange a meeting", "propose a time",
    "alternative times", "scheduling link", "calendar invite", "could we schedule",
)
_CONFIRM_PHRASES = (
    "works for me", "that works", "i'll be available", "i am available on",
    "i'm available on", "let's meet", "let's schedule", "see you on", "see you at",
    "confirm", "sounds good for", "book", "slot",
)
_TIME_RE = re.compile(
    r"\b\d{1,2}:\d{2}\s*(?:am|pm)?\b|\b\d{1,2}\s*(?:am|pm)\b",
    re.I,
)
_DATE_RE = re.compile(
    r"\b(?:today|tomorrow)\b|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}"
    r"(?:st|nd|rd|th)?(?:,?\s*\d{4})?\b|"
    r"\b\d{1,2}(?:st|nd|rd|th)?\s+"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?:,?\s*\d{4})?\b",
    re.I,
)


def is_scheduling_request(text: str) -> bool:
    lower = text.lower()
    return any(p in lower for p in _SCHEDULE_PHRASES)


def _has_clock_time(text: str) -> bool:
    """True when text contains an explicit clock time (not substring noise like 'timelines')."""
    if _TIME_RE.search(text):
        return True
    if re.search(r"\b\d{1,2}\s*(?:am|pm)\b", text, re.I):
        return True
    if re.search(r"\b\d{1,2}:\d{2}\b", text):
        return True
    return bool(_TZ_RE.search(text))


def _has_weekday(text: str) -> bool:
    """Match whole weekday tokens only — avoids 'mon' inside 'commonly'."""
    return bool(_WEEKDAY_RE.search(text))


def has_proposed_meeting_time(text: str) -> bool:
    """True when the prospect names a specific date and/or time for a call."""
    lower = text.lower()
    has_weekday = _has_weekday(text)
    has_month_date = bool(_DATE_RE.search(text))
    has_clock_time = _has_clock_time(text)

    if has_weekday and has_clock_time:
        return True
    if has_month_date and has_clock_time:
        return True
    if re.search(r"\btoday\b", lower) and has_clock_time:
        return True
    if is_scheduling_request(text) and has_clock_time and (has_month_date or has_weekday):
        return True
    if any(p in lower for p in _CONFIRM_PHRASES) and (
        has_clock_time or has_month_date or has_weekday
    ):
        return True
    return False


def strip_quoted_reply(body: str) -> str:
    """Keep only the prospect's new text; drop quoted thread content."""
    if not body:
        return ""

    lines = body.splitlines()
    clean: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">"):
            break
        if re.match(r"^On .+ wrote:$", stripped, re.I):
            break
        if stripped.startswith("-----Original Message-----"):
            break
        if re.match(r"^From:\s", stripped, re.I) and clean:
            break
        clean.append(line)

    text = "\n".join(clean).strip()

    # Trailing unquoted agent reply (some clients omit > markers)
    match = re.search(r"\n\s*Hi\s+[\w.-]+,?\s*$", text, re.I | re.M)
    if match and match.start() > len(text) * 0.25:
        text = text[: match.start()].strip()

    return text


def requests_more_details(text: str) -> bool:
    lower = text.lower()
    return any(p in lower for p in _DETAIL_PHRASES)


def wants_more_info(text: str) -> bool:
    """Prospect asked about approach/services before committing to a call."""
    if requests_more_details(text):
        return True
    lower = text.lower()
    word_count = len(text.split())
    _info_indicators = (
        "challenge", "interested in learning", "interested in", "tell me more",
        "would like to know", "how your team", "how you have", "success stor",
        "our current", "we are focused", "look forward to hearing", "governance",
        "compliance", "metadata", "pain point", "struggle", "issue", "approach",
        "framework", "services you offer", "additional details", "share more",
        "explore potential", "collaboration", "looking at improving", "dealing with",
        "inconsistent data", "data quality",
    )
    has_indicator = any(i in lower for i in _info_indicators)
    return has_indicator and ("?" in text or word_count >= 15)


def mentioned_days(text: str) -> set[str]:
    lower = text.lower()
    return {day for day in _DAYS if day in lower}


_KNOWN_CLIENTS = (
    "Ministry of Finance Dubai", "Vodafone", "Deloitte", "KPMG", "Capgemini",
    "DEWA", "TAWAL",
)


def strip_unmentioned_clients(body: str, allowed: list[str]) -> str:
    """Remove client name-drops that were not mentioned in this email thread."""
    allowed_lower = {c.lower() for c in allowed}
    for client in _KNOWN_CLIENTS:
        if client.lower() in allowed_lower:
            continue
        if client.lower() not in body.lower():
            continue
        body = re.sub(
            rf"(?i)[^.?!]*\b{re.escape(client)}\b[^.?!]*[.?!]?\s*",
            "",
            body,
        )
        body = re.sub(rf"(?i)\b{re.escape(client)}\b", "", body)
    body = re.sub(r"\s{2,}", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


_CLIENT_PATTERN = re.compile(
    r"(?:work with|worked with|helped|achieved for organizations such as|"
    r"clients like|such as)\s+([A-Z][A-Za-z0-9\s&.'-]{1,40}?)"
    r"(?:,\s*(?:a|an|the)\s+|\s+has\s+|\s+have\s+|\.|,|\s+—)",
    re.I,
)


def extract_case_study_clients(history: list) -> list[str]:
    """Pull client/org names referenced anywhere in the thread."""
    clients: list[str] = []
    for msg in history:
        body = msg.get("body", "")
        for match in _CLIENT_PATTERN.finditer(body):
            name = match.group(1).strip().rstrip(",.")
            if name and name not in clients:
                clients.append(name)
        lower = body.lower()
        for client in _KNOWN_CLIENTS:
            if client.lower() in lower and client not in clients:
                clients.append(client)
    return clients


def strip_instruction_placeholders(body: str, *, keep_zoom: bool = False) -> str:
    """Remove leaked [bracket] instructions from LLM output."""
    if keep_zoom:
        body = body.replace("[ZOOM_LINK]", "\x00ZOOM\x00")
    body = re.sub(r"\[[^\]]+\]", "", body)
    if keep_zoom:
        body = body.replace("\x00ZOOM\x00", "[ZOOM_LINK]")
    return body


def inject_case_study_clients(body: str, clients: list[str]) -> str:
    """Replace vague client references with names from the thread."""
    if not clients:
        return body

    primary = clients[0]
    outcome = (
        f"For example, our work with {primary} delivered measurable improvements "
        f"in data quality and compliance."
    )

    body = re.sub(
        r"(?i)we(?:'ve| have) had success with clients? in similar industries[^.?!]*[.?!]?",
        outcome,
        body,
    )
    body = re.sub(
        r"(?i)clients? in similar industries[^.?!]*[.?!]?",
        outcome,
        body,
    )
    body = re.sub(r"(?i),\s*such as\s*\.?", ".", body)
    body = re.sub(r"(?i)such as\s*\.?", "", body)

    if primary.lower() not in body.lower():
        body = body.rstrip()
        if body and not body.endswith((".", "!", "?")):
            body += "."
        body += f" {outcome}"

    return body


def _strip_invented_meeting_confirmations(body: str) -> str:
    """Remove meeting-link / confirmation phrasing when no call was agreed."""
    patterns = (
        r"(?i)\b(?:here(?:'s| is) the (?:zoom )?meeting (?:link|invite)|meeting link below|calendar invite|zoom meeting invite)[^.?!:\n]*[.?!:\n]?\s*",
        r"(?i)\b(?:i(?:'ve| have) (?:set up|scheduled|confirmed)|confirmed our call(?: at)?)[^.?!]*[.?!]?\s*",
        r"(?i)\bi(?:'m| am) excited to (?:discuss|meet|speak|connect|learn more about)[^.?!]*[.?!]?\s*",
        r"(?i)\b(?:for our call|our (?:upcoming )?call|join (?:us|me) (?:on|at))[^.?!]*[.?!]?\s*",
        r"(?i)\blooking forward to (?:it|our call|speaking|the call)[^.?!]*[.?!]?\s*",
        r"(?i)\bnext\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)[^.?!]*[.?!]?\s*",
    )
    for pattern in patterns:
        body = re.sub(pattern, "", body)

    body = re.sub(r"\s+\.", ".", body)
    body = re.sub(r"\.\s*\.", ".", body)
    body = re.sub(r",\s*\.", ".", body)
    body = re.sub(r":\s*(?=\n|$)", "", body)
    body = re.sub(r"^\s*Hi\s+[^,\n]+,\s*\.?\s*", "", body, flags=re.I | re.M)
    return body.strip()


def reply_has_unauthorized_scheduling(
    reply_body: str, prospect_reply: str, situation: str
) -> bool:
    """True when agent output mentions scheduling but prospect did not."""
    if situation == "send_zoom":
        return False

    lower = reply_body.lower()
    prospect_scheduled = (
        has_proposed_meeting_time(prospect_reply)
        or is_scheduling_request(prospect_reply)
    )
    if prospect_scheduled:
        return False

    scheduling_markers = (
        "meeting link", "zoom meeting", "teams link", "calendar invite",
        "meeting invite", "join url", "our call at", "our call on",
        "confirmed our call", "scheduled for", "see you on", "see you at",
    )
    if any(m in lower for m in scheduling_markers):
        return True
    if _has_weekday(reply_body) and not _has_weekday(prospect_reply):
        return True
    if _has_clock_time(reply_body) and not _has_clock_time(prospect_reply):
        return True
    return False


def sanitize_scheduling_language(
    reply_body: str, prospect_reply: str, situation: str
) -> str:
    """Remove day/time references the prospect never mentioned."""
    if situation == "send_zoom":
        return reply_body

    prospect_days = mentioned_days(prospect_reply)
    prospect_has_time = _has_clock_time(prospect_reply)
    body = reply_body

    for day in _DAYS:
        if day in body.lower() and day not in prospect_days:
            body = re.sub(
                rf"(?i)\b(?:next\s+)?{day}(?:\s+or\s+(?:next\s+)?\w+day)?\b",
                "",
                body,
            )
            body = re.sub(rf"(?i)\bor\s+{day}\b", "", body)

    body = re.sub(
        r"(?i)\b(?:next\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r"(?:\s+or\s+(?:next\s+)?(?:monday|tuesday|wednesday|thursday|friday))?\b",
        "",
        body,
    )

    if not prospect_has_time:
        body = re.sub(
            r"(?i)\b(?:at|on)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b",
            "",
            body,
        )
        body = re.sub(
            r"(?i)\b(?:at|on)\s+\d{1,2}\s*(?:am|pm)\b",
            "",
            body,
        )

    body = _strip_invented_meeting_confirmations(body)
    body = re.sub(r"(?i)please let me know which day works best[^.?!]*[.?!]?", "", body)
    body = re.sub(r"(?i)would you be available for a quick call\s*\?", "", body)
    body = re.sub(
        r"(?i)(?:perhaps we could schedule|schedule)\s+for\s+next week[^.?!]*[.?!]?",
        "",
        body,
    )
    body = re.sub(
        r"(?i)would you be open to[^.?!]*(?:next week|this week)[^.?!]*[.?!]?",
        "",
        body,
    )
    body = re.sub(r"(?i)\bbrief call next\s*\?", "brief call?", body)
    body = re.sub(r"(?i)\bnext\s*\?", "?", body)
    body = re.sub(r"(?i)\bnext\s+(?=[.?!])", "", body)
    body = re.sub(r"\s{2,}", " ", body)
    body = re.sub(r" +\n", "\n", body)
    body = body.strip()

    lower = body.lower()
    if situation == "ask_availability" and "work best" not in lower:
        body = body.rstrip()
        if body and not body.endswith((".", "!", "?")):
            body += "."
        body += " What days and times work best for you?"

    if situation == "more_info":
        if not re.search(r"(?i)would you be open to|brief call|happy to (?:walk|discuss)", body):
            body = body.rstrip()
            if body and not body.endswith((".", "!", "?")):
                body += "."
            body += " Would you be open to a brief call to explore how this applies to your environment?"

    return body.strip()


def polish_reply_body(
    body: str,
    prospect_reply: str,
    situation: str,
    thread_history: Optional[list] = None,
) -> str:
    """Final cleanup: placeholders, client names, scheduling language."""
    if situation == "send_zoom":
        return strip_instruction_placeholders(body, keep_zoom=True).strip()

    clients = extract_case_study_clients(thread_history or [])
    keep_zoom = False

    body = strip_instruction_placeholders(body, keep_zoom=keep_zoom)
    body = body.replace("[ZOOM_LINK]", "").strip()
    body = strip_unmentioned_clients(body, clients)
    body = inject_case_study_clients(body, clients)
    body = sanitize_scheduling_language(body, prospect_reply, situation)
    body = re.sub(r"\n\s*www\.bitsglobalconsulting\.com\s*$", "", body, flags=re.I | re.M)
    body = re.sub(r"\n\s*\*\s+", "\n- ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()
