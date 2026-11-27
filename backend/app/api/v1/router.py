"""v1 router registry. Feature routers are added here in later stages."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    admin_commission,
    admin_content,
    admin_finance,
    admin_moderation,
    admin_system,
    auth,
    bookings,
    catalog,
    customers,
    meta,
    notifications,
    owner_business,
    owner_kyc,
    owner_resources,
    owner_venues,
    owners,
    payments,
    places,
    profiles,
    reviews,
)

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(auth.router)
api_router.include_router(profiles.router)
api_router.include_router(profiles.support_router)
api_router.include_router(customers.router)
api_router.include_router(owners.router)
api_router.include_router(owner_business.router)
api_router.include_router(owner_venues.router)
api_router.include_router(owner_resources.router)
api_router.include_router(admin.router)
api_router.include_router(admin_system.router)
api_router.include_router(admin_finance.router)
api_router.include_router(admin_commission.router)
api_router.include_router(admin_commission.export_router)
api_router.include_router(admin_moderation.router)
api_router.include_router(admin_content.router)
api_router.include_router(admin_content.public_router)
api_router.include_router(owner_kyc.router)
api_router.include_router(catalog.router)
api_router.include_router(bookings.router)
api_router.include_router(payments.router)
api_router.include_router(reviews.router)
api_router.include_router(places.router)
api_router.include_router(notifications.router)
