"""Search helpers shared by the admin queries."""


def like_pattern(q: str) -> str:
    """Contains-pattern for ILIKE ... ESCAPE '\\'. Wildcards typed by the user match literally."""
    return "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
