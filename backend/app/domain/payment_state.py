"""Payment status machine. Every change to `payments.status` is checked here.

created -> pending -> authorized -> captured -> (partially_)refunded
                  \\-> failed -> (the same order may be retried) -> pending / authorized / captured

`failed` is NOT terminal because Razorpay lets a customer retry on the same order until it is paid.
`captured` can never go back to failed or pending: a late or repeated "failed" signal is ignored.
Refund states are reached only when the gateway reports a refund; no refund is ever started by
this system (no refund policy is approved: open question Q9).
"""

CREATED = "created"
PENDING = "pending"
AUTHORIZED = "authorized"
CAPTURED = "captured"
FAILED = "failed"
REFUNDED = "refunded"
PARTIALLY_REFUNDED = "partially_refunded"

TRANSITIONS: dict[str, frozenset[str]] = {
    CREATED: frozenset({PENDING, AUTHORIZED, CAPTURED, FAILED}),
    PENDING: frozenset({AUTHORIZED, CAPTURED, FAILED}),
    AUTHORIZED: frozenset({CAPTURED, FAILED}),
    FAILED: frozenset({PENDING, AUTHORIZED, CAPTURED}),
    CAPTURED: frozenset({REFUNDED, PARTIALLY_REFUNDED}),
    PARTIALLY_REFUNDED: frozenset({PARTIALLY_REFUNDED, REFUNDED}),
    REFUNDED: frozenset(),
}

#: Statuses where the customer may still pay on this order.
OPEN = frozenset({CREATED, PENDING, AUTHORIZED, FAILED})
#: Statuses that mean money was taken.
PAID = frozenset({CAPTURED, REFUNDED, PARTIALLY_REFUNDED})


def can_move(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, frozenset())
