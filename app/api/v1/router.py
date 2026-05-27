"""Versioned API router."""

from fastapi import APIRouter

from app.api.v1.routers import auth, authors, books, users


# Aggregate v1 routers in a single entry point.
api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(authors.router)
api_router.include_router(books.router)
api_router.include_router(users.router)
