"""Versioned API router."""

from fastapi import APIRouter

from app.api.v1.routers import auth, users


# Aggregate v1 routers in a single entry point.
api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
