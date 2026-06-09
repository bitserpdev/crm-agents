"""Shared plain-text structuring and HTML rendering for outbound emails."""

import re
from typing import Optional

_SIGNATURE_RE = re.compile(
    r"(Warm regards,|Best regards,|Kind regards,|Regards,|Best,)\s*"
    r"(BITS Global Consulting(?:\s+Team)?)\s*(www\.\S+)?\s*$",
    re.I | re.M,
)
_GREETING_RE = re.compile(r"^((?:Dear|Hi)\s+[^,]+,)\s*(.*)$", re.I | re.S)
_CLIENT_NAMES = (
    "Vodafone", "Deloitte", "KPMG", "Capgemini",
    "Ministry of Finance Dubai", "DEWA", "TAWAL",
    "BITS Global Consulting",
)
_DEFAULT_SIGNATURE = (
    "Warm regards,\nBITS Global Consulting\nwww.bitsglobalconsulting.com"
)


def format_context_from_contact(contact: dict) -> dict:
    return {
        "company": contact.get("company_name", ""),
        "Company": contact.get("company_name", ""),
        "industry": contact.get("industry", ""),
        "job_title": contact.get("job_title", ""),
        "Job Title": contact.get("job_title", ""),
    }


def structure_email_text(text: str) -> str:
    """Turn flat LLM output into a properly formatted plain-text email."""
    text = text.strip()
    if not text:
        return text

    if text.count("\n\n") >= 2 and re.match(r"^(Dear|Hi)\s+", text):
        return re.sub(r"\n{3,}", "\n\n", text)

    signature = ""
    sig_match = _SIGNATURE_RE.search(text)
    if sig_match:
        website = sig_match.group(3) or "www.bitsglobalconsulting.com"
        signature = (
            f"{sig_match.group(1).strip()}\n"
            f"{sig_match.group(2).strip()}\n"
            f"{website.strip()}"
        )
        text = text[: sig_match.start()].strip()

    greeting, body = "", text
    greet_match = _GREETING_RE.match(text)
    if greet_match:
        greeting = greet_match.group(1).strip()
        body = greet_match.group(2).strip()

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
    questions = [s for s in sentences if s.endswith("?")]
    statements = [s for s in sentences if not s.endswith("?")]

    paragraphs: list[str] = []
    if len(statements) >= 2:
        mid = (len(statements) + 1) // 2
        paragraphs.append(" ".join(statements[:mid]))
        paragraphs.append(" ".join(statements[mid:]))
    elif statements:
        paragraphs.append(" ".join(statements))
    if questions:
        paragraphs.append(" ".join(questions))

    if not paragraphs and body:
        paragraphs = [body]

    blocks = []
    if greeting:
        blocks.append(greeting)
    blocks.extend(paragraphs)
    if signature:
        blocks.append(signature)
    elif blocks:
        blocks.append(_DEFAULT_SIGNATURE)

    return "\n\n".join(blocks)


def _highlight_keywords(text: str, context: Optional[dict] = None) -> str:
    keywords = set(_CLIENT_NAMES)
    if context:
        for key in ("company", "Company", "industry", "job_title", "Job Title"):
            val = str(context.get(key, "")).strip()
            if val and val not in ("[Company]", "your company", ""):
                keywords.add(val)

    for kw in sorted(keywords, key=len, reverse=True):
        pattern = re.compile(re.escape(kw), re.IGNORECASE)
        text = pattern.sub(
            lambda m: (
                f"<span style='color:#16a34a;font-weight:600;'>{m.group(0)}</span>"
            ),
            text,
        )
    return text


def _inline_to_html(text: str, context: Optional[dict] = None) -> str:
    text = _highlight_keywords(text, context)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^\)]+)\)",
        r'<a href="\2" style="color:#4F46E5;">\1</a>',
        text,
    )
    text = re.sub(
        r'(?<!href=")(https?://[^\s<]+)',
        r'<a href="\1" style="color:#4F46E5;">\1</a>',
        text,
    )
    return text.replace("\n", "<br>")


def build_html_from_text(text: str, context: Optional[dict] = None) -> str:
    """Convert structured plain text into a proper HTML email."""
    structured = structure_email_text(text)
    blocks = [b.strip() for b in structured.split("\n\n") if b.strip()]

    body_parts: list[str] = []
    signature_html = ""

    for block in blocks:
        if re.match(r"^(Dear|Hi)\s+[^,]+,", block):
            body_parts.append(
                f"<p style='margin:0 0 16px;'><strong>"
                f"{_inline_to_html(block, context)}</strong></p>"
            )
        elif re.match(
            r"^(Warm regards,|Best regards,|Kind regards,|Regards,|Best,)",
            block,
            re.I,
        ):
            signature_html = (
                f"<p style='margin:24px 0 0; color:#555; line-height:1.6;'>"
                f"{_inline_to_html(block, context)}</p>"
            )
        else:
            body_parts.append(
                f"<p style='margin:0 0 16px; line-height:1.6;'>"
                f"{_inline_to_html(block, context)}</p>"
            )

    if not signature_html:
        signature_html = (
            "<p style='margin:24px 0 0; color:#555; line-height:1.6;'>"
            "Warm regards,<br>"
            "<strong>BITS Global Consulting</strong><br>"
            '<a href="https://www.bitsglobalconsulting.com" '
            'style="color:#4F46E5;">www.bitsglobalconsulting.com</a></p>'
        )

    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;'
        'color:#333;line-height:1.6;max-width:600px;margin:0 auto;">'
        f"{''.join(body_parts)}{signature_html}"
        "</div>"
    )


def format_email_body(
    body: str, context: Optional[dict] = None
) -> tuple[str, str]:
    """Return (structured plain text, HTML) for sending."""
    structured = structure_email_text(body)
    html = build_html_from_text(structured, context)
    return structured, html
