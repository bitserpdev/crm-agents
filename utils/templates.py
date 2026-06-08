import os
from pathlib import Path

def load_template(template_name: str) -> str:
    """Load HTML template from file."""
    template_path = Path(__file__).parent.parent / "templates" / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()