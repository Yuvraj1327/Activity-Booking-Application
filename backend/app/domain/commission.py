"""Commission rule resolution: pure functions, no database.

Priority (first match wins, exactly ONE rule is applied per booking):
    1. venue-specific rule
    2. activity-specific rule (the venue's category)
    3. global default rule
A rule that is deactivated (or has no version in force yet) is skipped and the next scope is tried.

A venue can have several activities. When more than one of them has an active activity rule the
percentages differ, which one applies is an OPEN CLIENT DECISION. Until a tie-break ("lowest" / "highest")
is configured the booking is flagged ambiguous, gets no rate, and is not accrued. Nothing is guessed.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

Scope = Literal["venue", "activity", "global"]
DEFAULT_PRIORITY: tuple[Scope, ...] = ("venue", "activity", "global")
DEFAULT_ACTIVITY_TIEBREAK: str | None = None  # None = unresolved: not chosen for the client
SCOPES = frozenset(DEFAULT_PRIORITY)


@dataclass(frozen=True)
class Candidate:
    """A rule version in force at the resolution time."""

    scope: str
    rule_id: Any
    version_id: Any
    version: int
    bps: int
    is_active: bool
    category_id: Any = None
    category_slug: str | None = None


def validate_priority(priority: Sequence[str]) -> tuple[Scope, ...]:
    """A priority is a permutation of the three scopes: nothing missing, nothing repeated (no ambiguity)."""
    if sorted(priority) != sorted(SCOPES):
        raise ValueError("priority must list venue, activity and global exactly once each")
    return tuple(cast(Scope, p) for p in priority)


def resolve(
    candidates: Sequence[Candidate],
    priority: Sequence[str] = DEFAULT_PRIORITY,
    activity_tiebreak: str | None = DEFAULT_ACTIVITY_TIEBREAK,
) -> tuple[Candidate | None, bool]:
    """(the single rule that applies or None, ambiguous). `ambiguous` is True when several activity rules with
    DIFFERENT percentages compete and no tie-break is approved: nothing is chosen and lower scopes are NOT used."""
    order = validate_priority(priority)
    for scope in order:
        active = [c for c in candidates if c.scope == scope and c.is_active]
        if not active:
            continue
        if scope == "activity" and len({c.bps for c in active}) > 1:
            if activity_tiebreak not in ("lowest", "highest"):
                return None, True
            sign = 1 if activity_tiebreak == "lowest" else -1
            active.sort(key=lambda c: (sign * c.bps, c.category_slug or "", str(c.rule_id)))
        else:
            active.sort(key=lambda c: (c.category_slug or "", str(c.rule_id)))
        return active[0], False
    return None, False


def pick(
    candidates: Sequence[Candidate],
    priority: Sequence[str] = DEFAULT_PRIORITY,
    activity_tiebreak: str | None = DEFAULT_ACTIVITY_TIEBREAK,
) -> Candidate | None:
    return resolve(candidates, priority, activity_tiebreak)[0]


def commission_paise(base_paise: int, bps: int) -> int:
    """Integer paise, half-up (the single rounding rule used everywhere money is split)."""
    from app.domain.finance_math import mul_bps

    return mul_bps(base_paise, bps)
