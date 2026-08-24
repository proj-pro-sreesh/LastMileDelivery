# Last-Mile Delivery Tracker

Delivery management platform for last-mile logistics: customers book parcels, admins configure zones/rates and manage assignments, delivery agents execute deliveries — with rule-driven pricing, deterministic nearest-agent assignment, immutable tracking history, failed-delivery rescheduling and notifications.

**Stack:** FastAPI · SQLAlchemy · Alembic · PostgreSQL 18 · Next.js 16 (App Router) · TypeScript · Tailwind CSS v4

## Features

| Area | What it does |
| --- | --- |
| Auth | JWT login/register, bcrypt hashes, role-based access (`CUSTOMER` / `AGENT` / `ADMIN`) enforced server-side on every route |
| Pricing | Volumetric vs actual weight (chargeable ceils to whole kg), zone pair rate cards (intra-zone = same-zone card), B2B/B2C rates, COD surcharges — all DB-driven, no hardcoded prices; missing config → HTTP 422 |
| Orders | Live quote preview → booking → ownership-scoped detail with append-only tracking timeline (DB trigger makes history immutable) |
| Assignment | Admin manual assign or one-click auto-assign: AVAILABLE agents only, ranked by pickup-zone match → Haversine distance to pickup coordinates → user id (fully deterministic); assignment flips agent BUSY; any terminal status releases them |
| Lifecycle | Strict state machine; agents get forward edges only; admin can override anywhere (remarks required) except FAILED→PENDING which is reserved for the reschedule endpoint |
| Failures & retries | FAILED consumes a delivery attempt and frees the agent; reschedule returns the order to the queue with a fresh redelivery date (default tomorrow, past dates rejected) |
| Notifications | In-app feed + simulated email/SMS (mock mode default, `NOTIFICATIONS_MODE=disabled` to switch off): assignment (customer + agent), every status change, failure reasons, redelivery notices |

## Quick start

### Option A — Docker (everything in containers)

```bash
docker compose up -d --build          # db + backend (auto-migrates) + frontend
docker compose exec backend python scripts/seed.py   # demo data (idempotent)
```

- Frontend: http://localhost:3000
- API docs (Swagger): http://localhost:8000/docs

### Option B — Local development

Requires Python 3.14, Node 20+, and a local PostgreSQL 18 on :5432.

```bash
# backend
createdb lastmile_delivery                     # once
cd backend
python3.14 -m venv ../.venv && ../.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                           # DATABASE_URL defaults to socket auth
../.venv/bin/alembic upgrade head              # schema (incl. immutability trigger)
../.venv/bin/python scripts/seed.py            # zones, rates, demo users
../.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev                                    # http://localhost:3000
```

### Demo accounts (after seeding)

| Role | Email | Password |
| --- | --- | --- |
| Admin | `admin@lastmile-demo.com` | `Admin@123` |
| Agent | `agent.vijay@lastmile-demo.com` | `Agent@123` |
| Agent | `agent.priya@lastmile-demo.com` | `Agent@123` |

Customers self-register at `/register`.

## API overview

Base URL `/`, JSON everywhere, JWT via `Authorization: Bearer <token>`.

| Method & path | Who | Purpose |
| --- | --- | --- |
| `POST /auth/register` · `POST /auth/login` · `GET /auth/me` | public/authed | account lifecycle (register always creates CUSTOMERs) |
| `GET /health` | public | service + database probe |
| `POST /orders/quote` · `POST /orders` | customer/admin | price preview and booking (admin may book on behalf of a customer) |
| `GET /orders` · `GET /orders/{id}` · `GET /orders/{id}/tracking` | scoped by role | list/detail/timeline with server-side ownership checks |
| `PATCH /agent/orders/{id}/status` | agent | advance own orders one legal step; FAILED requires a reason |
| `GET /agent/orders` · `PATCH /agent/availability` · `PATCH /agent/location` | agent | workspace endpoints |
| `POST /admin/orders/{id}/assign` · `.../auto-assign` | admin | manual and nearest-agent assignment |
| `PATCH /admin/orders/{id}/status` | admin | override with mandatory remarks (FAILED→PENDING rejected — use reschedule) |
| `POST /admin/orders/{id}/reschedule` | admin | failed order back to the queue, new redelivery date |
| `GET /admin/agents` | admin | roster with availability and active load |
| CRUD `/admin/zones` `/admin/areas` `/admin/rates` `/admin/cod-rates` | admin | pricing configuration |
| `GET /notifications` (`?unread=true`) · `POST /notifications/{id}/read` · `POST /notifications/read-all` | authed | owner-scoped notification feed |

Full request/response schemas are documented interactively at `/docs`.

## Business rules worth knowing

- **Single pricing source of truth:** quote endpoint and order creation both call `rate_engine.calculate_quote()`; intra-zone = a rate-card row whose `from_zone_id = to_zone_id`; each pincode maps to exactly one zone.
- **Immutable history:** `order_tracking` rows are protected by a Postgres trigger — UPDATE/DELETE raise at the database level, not just in app code.
- **State machine:** all transitions go through `app/services/state_machine.py`; entering FAILED increments `delivery_attempt`; terminal statuses release the assigned agent.
- **Deterministic auto-assign:** `(pickup-zone match desc, Haversine distance asc, user_id asc)` — same inputs always pick the same agent.
- **Tests build the schema via Alembic migrations**, so triggers and constraints are exercised exactly as in production.

## Tests

```bash
.venv/bin/python -m pytest backend/tests -q     # from repo root; 83 tests
```

The suite recreates an isolated `lastmile_delivery_test` database per session via migrations.

## Project structure

```
backend/
├── app/
│   ├── core/         settings, DB session, security (JWT/bcrypt), RBAC deps
│   ├── models/       SQLAlchemy ORM (users, zones, areas, rate_cards, cod_rates,
│   │                 orders, order_tracking, agent_profiles, notifications)
│   ├── schemas/      pydantic request/response models
│   ├── services/     business logic: auth, zone, rate_engine, pricing, order,
│   │                 tracking, state_machine, assignment, notification
│   └── routers/      thin HTTP layers delegating to services
├── alembic/          migrations (schema + DB-level trigger live here)
├── scripts/seed.py   idempotent demo/reference data
└── tests/            pytest suite (API-level, isolated test DB)

frontend/
├── app/              routes: /login /register /orders /orders/[id] /agent /admin
├── components/       AuthProvider, AppShell, Timeline, StatusBadge, NotificationBell
└── lib/              typed fetch client, domain types, formatters
```

## Configuration

Backend reads `.env` (see `backend/.env.example`):

| Variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg:///lastmile_delivery` | unix-socket local dev |
| `SECRET_KEY` | auto-generated (dev only) | must be set when `ENVIRONMENT=production` |
| `ENVIRONMENT` | `development` | |
| `CORS_ORIGINS` | `http://localhost:3000` | comma-separated |
| `NOTIFICATIONS_MODE` | `mock` | `disabled` turns off in-app rows and mock transports |

Frontend reads `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`) — note it is baked into the client bundle at **build time** (pass as a Docker build arg).
