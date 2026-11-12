"""Customer payments (Razorpay) and the gateway webhook.

The webhook route is intentionally unauthenticated by JWT: it is authenticated by the HMAC signature
of the RAW request body (X-Razorpay-Signature) using a webhook secret that is separate from the API
secret. The raw bytes are read before any JSON parsing.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Header, Query, Request

from app.api.deps import CustomerUser, DbSession
from app.schemas.catalog import Limit
from app.schemas.payment import (
    CreateOrderOut,
    CreateOrderRequest,
    PaymentOut,
    PaymentPage,
    VerifyPaymentRequest,
    WebhookAck,
)
from app.services.dispatch import dispatch_in_background
from app.services.payments import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])


def _svc(request: Request, session: DbSession) -> PaymentService:
    return PaymentService(session, request.app.state.settings, request.app.state.payment_gateway)


@router.post("/create-order", response_model=CreateOrderOut, summary="Create (or reuse) the Razorpay order")
async def create_order(
    body: CreateOrderRequest, request: Request, user: CustomerUser, session: DbSession
) -> CreateOrderOut:
    """The amount is computed on the server from the booking. Calling again for the same booking
    returns the same order, so a double tap or a retry never creates a second payment."""
    return await _svc(request, session).create_order(user, body.booking_id)


@router.post("/verify", response_model=PaymentOut, summary="Verify a checkout result with the backend")
async def verify(
    body: VerifyPaymentRequest,
    request: Request,
    user: CustomerUser,
    session: DbSession,
    background: BackgroundTasks,
) -> PaymentOut:
    out = await _svc(request, session).verify(
        user, body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature
    )
    background.add_task(dispatch_in_background, request.app)
    return out


@router.post("/webhook", response_model=WebhookAck, summary="Razorpay webhook (signature-authenticated)")
async def webhook(
    request: Request,
    session: DbSession,
    background: BackgroundTasks,
    x_razorpay_signature: Annotated[str | None, Header()] = None,
    x_razorpay_event_id: Annotated[str | None, Header()] = None,
) -> WebhookAck:
    raw = await request.body()  # RAW bytes: the signature is computed over exactly these
    outcome = await _svc(request, session).handle_webhook(raw, x_razorpay_signature, x_razorpay_event_id)
    background.add_task(dispatch_in_background, request.app)
    return WebhookAck(outcome=outcome)


@router.get("/history", response_model=PaymentPage, summary="My payment history")
async def history(
    request: Request,
    user: CustomerUser,
    session: DbSession,
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> PaymentPage:
    return await _svc(request, session).history(user.id, limit, offset)


@router.get(
    "/{payment_id}",
    response_model=PaymentOut,
    summary="One of my payments (re-checks the gateway if pending)",
)
async def get_payment(
    payment_id: UUID,
    request: Request,
    user: CustomerUser,
    session: DbSession,
    background: BackgroundTasks,
) -> PaymentOut:
    out = await _svc(request, session).get_mine(user.id, payment_id)
    background.add_task(dispatch_in_background, request.app)
    return out
