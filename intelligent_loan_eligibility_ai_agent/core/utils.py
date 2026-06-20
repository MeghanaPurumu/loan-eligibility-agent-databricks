from __future__ import annotations

def parse_number(value, default=None):
    try:
        if value is None or value == "":
            return default
        if isinstance(value, (int, float)):
            return value
        s = str(value).replace(",", "").strip()
        if "." in s:
            return float(s)
        return int(s)
    except Exception:
        return default

def clamp_text(value: str, limit: int = 120) -> str:
    s = "" if value is None else str(value).strip()
    return s[:limit]

def normalize_employment(value: str) -> str:
    s = (value or "").strip().lower()
    mapping = {
        "salaried": "Salaried",
        "self-employed": "Self-employed",
        "self employed": "Self-employed",
        "business": "Business",
        "student": "Student",
        "unemployed": "Unemployed",
        "retired": "Retired",
    }
    return mapping.get(s, value.strip().title() if value else "")
