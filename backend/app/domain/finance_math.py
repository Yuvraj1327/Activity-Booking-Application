"""Money arithmetic for fees, tax, commission and refund reversals. Integer paise only, no floats.

Rounding is half-up (0.5 paise rounds away from zero) everywhere. Which rounding mode the
accountants want is part of Q7; it is isolated here so changing it touches one function.
"""

from dataclasses import dataclass
from typing import Literal

TaxOn = Literal["fee", "base_and_fee"]
BorneBy = Literal["platform", "owner"]


def mul_bps(amount: int, bps: int) -> int:
    """amount * bps / 10000, rounded half up."""
    return div_round(amount * bps, 10_000)


def div_round(numerator: int, denominator: int) -> int:
    """Integer division rounded half away from zero (works for negative numerators)."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    sign = -1 if numerator < 0 else 1
    n = abs(numerator)
    return sign * ((2 * n + denominator) // (2 * denominator))


@dataclass(frozen=True)
class Rules:
    platform_fee_bps: int
    platform_fee_fixed_paise: int
    tax_rate_bps: int
    tax_on: str
    commission_bps: int
    discount_borne_by: str


@dataclass(frozen=True)
class CustomerPrice:
    base: int
    fee: int
    tax: int
    discount: int
    total: int


def customer_price(base: int, discount: int, r: Rules) -> CustomerPrice:
    """What the customer pays. Fee on the base amount; tax on the fee, or on base + fee (before discount)."""
    fee = mul_bps(base, r.platform_fee_bps) + r.platform_fee_fixed_paise
    tax_base = fee if r.tax_on == "fee" else base + fee
    tax = mul_bps(tax_base, r.tax_rate_bps)
    return CustomerPrice(base, fee, tax, discount, base + fee + tax - discount)


@dataclass(frozen=True)
class Split:
    gross: int
    tax: int
    owner: int
    platform: int
    fee: int
    commission: int
    discount: int


def split_sale(gross: int, base: int, fee: int, tax: int, discount: int, r: Rules) -> Split:
    """Who gets what from one captured payment. owner + platform + tax == gross always."""
    if base + fee + tax - discount != gross:
        raise ValueError("price components do not add up to the amount paid")
    commission = mul_bps(base, r.commission_bps)
    owner = base - commission - (discount if r.discount_borne_by == "owner" else 0)
    platform = fee + commission - (discount if r.discount_borne_by == "platform" else 0)
    return Split(gross, tax, owner, platform, fee, commission, discount)


def reversal(sale_gross: int, sale_owner: int, sale_tax: int, refunded_total: int) -> tuple[int, int, int]:
    """Cumulative reversal after `refunded_total` has been refunded: (owner, tax, platform).
    Using cumulative totals keeps repeated partial refunds exactly consistent (no rounding drift)."""
    owner = div_round(sale_owner * refunded_total, sale_gross)
    tax = div_round(sale_tax * refunded_total, sale_gross)
    return owner, tax, refunded_total - owner - tax
