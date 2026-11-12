"""Reusable email templates. Plain Python, no secrets, every dynamic value is HTML-escaped."""

from collections.abc import Callable
from html import escape
from typing import Any

from app.gateways.resend import EmailMessage


def _money(paise: int, currency: str) -> str:
    symbol = "₹" if currency == "INR" else f"{currency} "
    return f"{symbol}{paise / 100:,.2f}"


def _layout(heading: str, lines: list[str]) -> tuple[str, str]:
    items = "".join(f"<p style='margin:0 0 10px'>{escape(line)}</p>" for line in lines)
    html = (
        "<div style='font-family:Arial,sans-serif;max-width:520px;margin:auto;padding:24px'>"
        f"<h2 style='margin:0 0 16px'>{escape(heading)}</h2>{items}"
        "<p style='color:#777;font-size:12px;margin-top:24px'>ZURUV. Discover. Book. Play.</p></div>"
    )
    return html, "\n\n".join([heading, *lines])


def _booking_lines(c: dict[str, Any]) -> list[str]:
    return [
        f"Booking code: {c['booking_code']}",
        f"Venue: {c['venue_name']} ({c['resource_name']})",
        f"When: {c['when']}",
    ]


def booking_confirmed(to: str, c: dict[str, Any]) -> EmailMessage:
    html, text = _layout("Your booking is confirmed", [*_booking_lines(c), "See you on the court!"])
    return EmailMessage(to, f"Booking confirmed: {c['booking_code']}", html, text)


def payment_received(to: str, c: dict[str, Any]) -> EmailMessage:
    lines = [
        f"We received your payment of {_money(int(c['amount_paise']), c['currency'])}.",
        *_booking_lines(c),
    ]
    html, text = _layout("Payment received", lines)
    return EmailMessage(to, f"Payment received for {c['booking_code']}", html, text)


def booking_cancelled(to: str, c: dict[str, Any]) -> EmailMessage:
    html, text = _layout("Your booking was cancelled", _booking_lines(c))
    return EmailMessage(to, f"Booking cancelled: {c['booking_code']}", html, text)


def owner_new_booking(to: str, c: dict[str, Any]) -> EmailMessage:
    lines = [*_booking_lines(c), f"Amount paid: {_money(int(c['amount_paise']), c['currency'])}"]
    html, text = _layout("New confirmed booking", lines)
    return EmailMessage(to, f"New booking at {c['venue_name']}", html, text)


def owner_booking_cancelled(to: str, c: dict[str, Any]) -> EmailMessage:
    html, text = _layout("A booking was cancelled", _booking_lines(c))
    return EmailMessage(to, f"Booking cancelled at {c['venue_name']}", html, text)


TEMPLATES: dict[str, Callable[[str, dict[str, Any]], EmailMessage]] = {
    "booking_confirmed": booking_confirmed,
    "payment_received": payment_received,
    "booking_cancelled": booking_cancelled,
    "owner_new_booking": owner_new_booking,
    "owner_booking_cancelled": owner_booking_cancelled,
}


def render(template: str, to: str, context: dict[str, Any]) -> EmailMessage:
    return TEMPLATES[template](to, context)
