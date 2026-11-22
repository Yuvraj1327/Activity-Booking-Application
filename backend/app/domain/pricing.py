"""Booking price calculation (backend only).

The owner-configured slot price is the base. Fees, tax and commission apply ONLY when an admin has
approved a finance configuration (Q7, Q8): without one they stay 0 and the note says so. A coupon
discount (validated on the server, see services/coupons.py) is applied on top. The result is stored
on the booking as `price_snapshot`, so later changes to prices, fees or coupons never alter an
existing booking.
"""

from typing import Any

from app.domain.finance_math import Rules, customer_price

PRICING_VERSION = 2
MIN_PAYABLE_PAISE = 100  # Razorpay's minimum order (INR 1.00): a discount can never take a booking below it


def quote(
    *,
    slot_price_paise: int,
    quantity: int,
    slot_minutes: int,
    currency: str = "INR",
    rules: Rules | None = None,
    config_version: int | None = None,
    discount_paise: int = 0,
    coupon_code: str | None = None,
) -> dict[str, Any]:
    if slot_price_paise < 0 or quantity < 1 or slot_minutes < 1 or discount_paise < 0:
        raise ValueError("invalid pricing input")
    base = slot_price_paise * quantity
    if rules is None:
        fee = tax = 0
        total = base - discount_paise
        note = "No fees or tax are configured."
    else:
        p = customer_price(base, discount_paise, rules)
        fee, tax, total = p.fee, p.tax, p.total
        note = f"Fees and tax follow finance configuration v{config_version}."
    if discount_paise:
        note += f" Coupon {coupon_code} applied."
    return {
        "version": PRICING_VERSION,
        "currency": currency,
        "slot_price_paise": slot_price_paise,
        "quantity": quantity,
        "slot_minutes": slot_minutes,
        "base_amount_paise": base,
        "fees_paise": fee,
        "tax_paise": tax,
        "discount_paise": discount_paise,
        "total_amount_paise": total,
        "finance_config_version": config_version,
        "coupon_code": coupon_code if discount_paise else None,
        "note": note,
    }
