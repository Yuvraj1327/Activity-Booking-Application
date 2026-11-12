import re

E164 = re.compile(r"^\+[1-9][0-9]{6,14}$")


def normalize_claim_phone(value: str | None) -> str | None:
    """Supabase stores verified phones without '+' (e.g. '919876543210'). Return E.164 or None."""
    if not value:
        return None
    candidate = value if value.startswith("+") else f"+{value}"
    return candidate if E164.match(candidate) else None
