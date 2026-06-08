import re
import json


def extract_json_from_llm(text: str) -> dict | None:
    if not text:
        return None

    # Strip markdown links [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

    # Strip markdown code fences
    text = re.sub(r"```(?:json)?", "", text).strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find outermost { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        print("[PARSER] No JSON object found in text")
        return None

    candidate = text[start:end + 1]

    # Try parsing candidate directly
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Fix unescaped literal newlines inside string values
    try:
        fixed = re.sub(r'(?<!\\)\n', r'\\n', candidate)
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    print("[PARSER] All strategies failed")
    return None