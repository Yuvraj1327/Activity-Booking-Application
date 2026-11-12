"""Booking status model (architecture section 9.4, proposal pending Q11).

Every status change goes through `check_transition`. Who may trigger which change is
explicit: customers can only cancel their own bookings; owners and admins cannot change
statuses at all yet (owner cancellation is unresolved, N22; admin tiers, Q18); payment-driven
changes belong to the system (Step 7) and are never accepted from a client.
"""

from app.core.errors import ConflictError

PENDING = "pending_payment"
FAILED = "payment_failed"
CONFIRMED = "confirmed"
EXPIRED = "expired"
CANCELLED_CUSTOMER = "cancelled_by_customer"
CANCELLED_OWNER = "cancelled_by_owner"
COMPLETED = "completed"
REFUND_PENDING = "refund_pending"
REFUNDED = "refunded"

#: Statuses that reserve the time slot (booking_slots.is_blocking = true).
BLOCKING = frozenset({PENDING, FAILED, CONFIRMED})
HOLDS = frozenset({PENDING, FAILED})
CANCELLED = frozenset({CANCELLED_CUSTOMER, CANCELLED_OWNER, REFUND_PENDING, REFUNDED})

TRANSITIONS: dict[str, frozenset[str]] = {
    PENDING: frozenset({CONFIRMED, EXPIRED, FAILED, CANCELLED_CUSTOMER}),
    FAILED: frozenset({PENDING, EXPIRED, CANCELLED_CUSTOMER}),
    CONFIRMED: frozenset({CANCELLED_CUSTOMER, CANCELLED_OWNER, COMPLETED}),
    CANCELLED_CUSTOMER: frozenset({REFUND_PENDING}),
    CANCELLED_OWNER: frozenset({REFUND_PENDING}),
    REFUND_PENDING: frozenset({REFUNDED}),
    EXPIRED: frozenset(),
    COMPLETED: frozenset(),
    REFUNDED: frozenset(),
}

#: Which actor may cause which target status. Anything not listed is refused.
ACTOR_TARGETS: dict[str, frozenset[str]] = {
    "customer": frozenset({CANCELLED_CUSTOMER}),
    "owner": frozenset(),  # N22 unresolved: owners cannot cancel or alter bookings
    "admin": frozenset(),  # Q18 unresolved
    "system": frozenset({CONFIRMED, EXPIRED, FAILED, PENDING, COMPLETED, REFUND_PENDING, REFUNDED}),
}


def is_blocking(status: str) -> bool:
    return status in BLOCKING


def check_transition(current: str, target: str, actor_role: str) -> None:
    if target not in TRANSITIONS.get(current, frozenset()):
        raise ConflictError(
            f"A booking that is '{current}' cannot become '{target}'.", code="INVALID_STATUS_TRANSITION"
        )
    if target not in ACTOR_TARGETS.get(actor_role, frozenset()):
        raise ConflictError(
            "You are not allowed to make this change to the booking.", code="TRANSITION_NOT_ALLOWED"
        )
