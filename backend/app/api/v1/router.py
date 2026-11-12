"""v1 router registry. Feature routers are added here in later stages."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    bookings,
    catalog,
    customers,
    meta,
    notifications,
    owner_business,
    owner_resources,
    owner_venues,
    owners,
    payments,
    profiles,
)

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(auth.router)
api_router.include_router(profiles.router)
api_router.include_router(customers.router)
api_router.include_router(owners.router)
api_router.include_router(owner_business.router)
api_router.include_router(owner_venues.router)
api_router.include_router(owner_resources.router)
api_router.include_router(admin.router)
api_router.include_router(catalog.router)
api_router.include_router(bookings.router)
api_router.include_router(payments.router)
api_router.include_router(notifications.router)
