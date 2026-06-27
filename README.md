# 📚 The Wisdom Vault — API

The backend for The Wisdom Vault bookstore. Built with **FastAPI**, **async SQLAlchemy**, **PostgreSQL**, and three isolated **Redis** instances. Paired with the [book-store-frontend](https://github.com/RashadDweik/book-store-frontend).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| Language | Python 3.12 |
| ORM | SQLAlchemy 2 (async) |
| Database Driver | asyncpg |
| Database | PostgreSQL 16 |
| Caching / Sessions | Redis 7 (3 isolated instances) |
| Migrations | Alembic |
| Auth | JWT (python-jose) — access + refresh token rotation |
| Password Hashing | Passlib `bcrypt_sha256` |
| Rate Limiting | SlowAPI |
| Logging | structlog (JSON in prod, console in debug) |
| Error Tracking | Sentry |
| Validation | Pydantic v2 |
| Testing | pytest + pytest-asyncio |
| Containerisation | Docker + Docker Compose |

---

## Architecture

The codebase follows a strict **Router → Service → Repository** layered pattern, with a domain model for each resource:

```
app/
├── api/v1/
│   └── routers/         # HTTP + WebSocket endpoints (auth, books, authors,
│                        #   categories, cart, orders, wishlist, users, realtime)
├── services/            # Business logic — one service per domain
├── repositories/        # Async SQLAlchemy queries — one repo per model
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic request/response schemas
└── core/
    ├── config.py        # Pydantic Settings loaded from .env
    ├── database.py      # Async engine + session factory
    ├── security.py      # JWT creation/decoding, bcrypt_sha256 hashing
    ├── dependencies.py  # FastAPI dependency helpers (e.g. require_admin)
    ├── inventory_cache.py   # Redis-backed book stock cache
    ├── refresh_token_store.py  # Redis-backed refresh token store (server-side revocation)
    ├── realtime.py      # In-memory WebSocket hub for live broadcasts
    └── limiter.py       # SlowAPI rate limiter instance
```

---

## Features

### Auth
- **Register / Login / Logout / Refresh** under `/api/v1/auth/`
- Access tokens (short-lived JWT) returned in JSON; refresh tokens stored in an **HttpOnly cookie** — JavaScript cannot read them
- **Server-side refresh token revocation** via a dedicated Redis instance (SHA-256 hashed token stored with TTL); logout immediately invalidates the session
- Refresh token rotation on every `/auth/refresh` call
- **Auth audit log** — every register/login/logout event is persisted with user ID, IP address, user agent, and a hashed token reference
- Rate limiting: 3 registrations/minute, 5 logins/minute per IP

### Books
- Full-text search (`q`), filter by category, author, price range, release date, and stock availability
- Pagination with `limit`/`offset`; total count returned in the `X-Total-Count` response header
- Book stock served from **Redis inventory cache** on reads; cache updated on every create/update/delete
- Admin-only create, update (PATCH), and delete endpoints
- On any stock change, a `book.stock.updated` or `book.stock.deleted` event is **broadcast to all connected WebSocket clients** via the inventory hub

### Real-time Inventory (`/ws/inventory`)
- WebSocket endpoint; any connected client receives live JSON events whenever book stock changes
- In-memory `WebSocketHub` with async lock; stale connections are silently pruned on broadcast failure

### Cart, Wishlist, Orders
- Full CRUD for cart items and wishlist items, scoped to the authenticated user
- Orders: create from cart, list history, retrieve detail, cancel

### Authors & Categories
- Browse and manage authors and categories

### Health Checks
- `GET /health` — lightweight liveness check
- `GET /ready` — verifies database connectivity and both Redis stores; returns `503` with a per-dependency status breakdown if any check fails

---

## Redis Instances

Three isolated Redis instances, each with a distinct role:

| Instance | Port | Purpose | Persistence |
|---|---|---|---|
| `redis-inventory` | 6379 | Book stock cache (`inventory:book-stock:<id>`) | None (evictable) |
| `redis-rate-limiter` | 6380 | SlowAPI rate limit counters | None (evictable) |
| `redis-refresh` | 6381 | Refresh token store (password-protected, SHA-256 keyed) | AOF (`everysec`) |

The refresh token store uses AOF persistence so revoked tokens survive a Redis restart.

---

## Database Migrations

Migrations are managed with Alembic, applied automatically on container startup.

| Migration | Change |
|---|---|
| `0001` | Initial tables (users, books, authors, categories, cart, wishlist, orders) |
| `0002` | Roles table and user role foreign key |
| `0003` | `full_name` column on users |
| `0004` | Auth audit log table |
| `0005` | `release_date` column on books |
| `0006` | Book category relationship |

---

## Getting Started

### With Docker (recommended)

```bash
git clone https://github.com/RashadDweik/book-store-api.git
cd book-store-api
cp .env.example .env   # edit values as needed
docker compose up --build
```

On first boot the container automatically:
1. Waits for PostgreSQL to be ready
2. Runs `alembic upgrade head`
3. Seeds the database (books, authors, categories)
4. Starts Uvicorn on port `8000`

The API will be available at [http://localhost:8000](http://localhost:8000).  
Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Local Development (without Docker)

#### Prerequisites

- Python 3.12+
- PostgreSQL 16
- Three Redis instances on ports `6379`, `6380`, `6381`

#### Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Create a `.env` file:

```env
DATABASE_URL=postgresql+asyncpg://bookshop:bookshop@localhost:5432/bookshop
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
REFRESH_COOKIE_NAME=refresh_token
REFRESH_COOKIE_SECURE=false
REFRESH_COOKIE_SAMESITE=lax
REFRESH_COOKIE_PATH=/
REDIS_URL=redis://localhost:6379
RATE_LIMIT_STORAGE_URI=redis://localhost:6380
REFRESH_TOKEN_REDIS_URL=redis://:dev-refresh-pass@localhost:6381/0
REDIS_REFRESH_PASSWORD=dev-refresh-pass
ALLOWED_ORIGINS=["http://localhost:3000"]
```

Run migrations and start the server:

```bash
alembic upgrade head
python scripts/seed_db.py
uvicorn app.main:app --reload
```

---

## Testing

```bash
pytest
```

The test suite covers unit tests for all repositories and services, plus integration tests for every API router. The conftest patches SlowAPI to use in-memory storage so rate limits don't interfere with test runs.

```
tests/
├── conftest.py
├── test_api_*_integration.py   # HTTP-level integration tests (auth, books, cart, wishlist, ...)
├── test_*_repository.py        # Repository unit tests
├── test_*_service.py           # Service unit tests
└── test_security.py            # JWT + password hashing tests
```

---

## API Reference

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | — | Register a new user |
| `POST` | `/api/v1/auth/login` | — | Login; issues access token + refresh cookie |
| `POST` | `/api/v1/auth/refresh` | Cookie | Rotate refresh token; issue new access token |
| `POST` | `/api/v1/auth/logout` | Cookie | Revoke refresh token and clear cookie |
| `GET` | `/api/v1/books` | — | List books (search, filter, paginate) |
| `GET` | `/api/v1/books/{id}` | — | Get book detail |
| `POST` | `/api/v1/books` | Admin | Create book |
| `PATCH` | `/api/v1/books/{id}` | Admin | Update book |
| `DELETE` | `/api/v1/books/{id}` | Admin | Delete book |
| `GET` | `/api/v1/authors` | — | List authors |
| `GET` | `/api/v1/categories` | — | List categories |
| `GET` | `/api/v1/cart` | JWT | Get cart |
| `POST` | `/api/v1/cart/items` | JWT | Add item to cart |
| `DELETE` | `/api/v1/cart/items/{id}` | JWT | Remove cart item |
| `GET` | `/api/v1/wishlist` | JWT | Get wishlist |
| `POST` | `/api/v1/wishlist/items` | JWT | Add to wishlist |
| `DELETE` | `/api/v1/wishlist/items/{id}` | JWT | Remove wishlist item |
| `GET` | `/api/v1/orders` | JWT | List orders |
| `GET` | `/api/v1/orders/{id}` | JWT | Order detail |
| `POST` | `/api/v1/orders` | JWT | Create order from cart |
| `PATCH` | `/api/v1/orders/{id}/cancel` | JWT | Cancel order |
| `GET` | `/api/v1/users/me` | JWT | Current user profile |
| `WS` | `/ws/inventory` | — | Live stock update stream |
| `GET` | `/health` | — | Liveness check |
| `GET` | `/ready` | — | Readiness check (DB + Redis) |

Full interactive documentation is available at `/docs` (Swagger UI) and `/redoc`.

---

## Frontend

See [book-store-frontend](https://github.com/RashadDweik/book-store-frontend) for the Next.js 16 / React 19 client that consumes this API.

---
