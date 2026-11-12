"""Booking price calculation (backend only).

Only the owner-configured slot price is applied. Fees, GST/tax, commission, discounts and
cancellation charges are NOT calculated because those rules are unapproved (Q7, Q8, N7, Q9).
The returned dict is stored on the booking as `price_snapshot`, so later changes to the
resource price never alter an existing booking.
"""

from typing import Any

PRICING_VERSION = 1


def quote(
    *, slot_price_paise: int, quantity: int, slot_minutes: int, currency: str = "INR"
) -> dict[str, Any]:
    if slot_price_paise < 0 or quantity < 1 or slot_minutes < 1:
        raise ValueError("invalid pricing input")
    base = slot_price_paise * quantity
    return {
        "version": PRICING_VERSION,
        "currency": currency,
        "slot_price_paise": slot_price_paise,
        "quantity": quantity,
        "slot_minutes": slot_minutes,
        "base_amount_paise": base,
        "fees_paise": 0,
        "tax_paise": 0,
        "discount_paise": 0,
        "total_amount_paise": base,
        "note": "No fees, tax or discounts are configured.",
    }
