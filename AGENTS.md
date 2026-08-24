# AGENTS.md — LastMileDelivery

## Project

- **Last-Mile Delivery Tracker**: FastAPI + SQLAlchemy/Alembic backend, Next.js/TS/Tailwind frontend, PostgreSQL 18. Take-home assignment; phases built sequentially — do not jump ahead of the agreed phase plan.
- Python **3.14** venv at repo root `.venv/` — always use it; never create another venv.
- Local Postgres runs via Homebrew on :5432; connect by unix socket as OS user: `postgresql+psycopg:///lastmile_delivery` (DB `lastmile_delivery`). TCP needs a password; socket does not.

## Commands

Run backend commands from `backend/`, tests from repo root:

```bash
# from repo root
.venv/bin/python -m pytest backend/tests -q

# from backend/
../.venv/bin/pip install -r requirements.txt -r requirements-dev.txt   # deps are pinned
../.venv/bin/python -m uvicorn app.main:app --reload --port 8000       # /health, /docs
../.venv/bin/alembic upgrade head                                      # migrations
```

- Backend settings load `backend/.env` regardless of CWD (`app/core/config.py`); copy `.env.example`.
- Alembic URL comes from app settings via `alembic/env.py`, not `alembic.ini`.
- `backend/tests/conftest.py` puts `backend/` on `sys.path`, auto-creates DB `lastmile_delivery_test`, and truncates all tables (`CASCADE`) after every test — new tables are covered automatically.
- Auth: JWT via `HTTPBearer`; protect routes with `Depends(require_role(UserRole.X))` from `app/core/deps.py`. `/auth/register` only ever creates CUSTOMERs — agents/admins come from `scripts/seed.py`.
- Emails stored lowercased (normalized in `auth_service`); duplicate → 409, bad creds → uniform 401 (no user enumeration).
- Pricing: `rate_engine.calculate_quote()` is the single source of truth — quote endpoint and order creation must both call it. Intra-zone rates are rate_cards rows with `from_zone_id = to_zone_id`; each pincode maps to exactly one zone (`areas.pincode` UNIQUE); chargeable weight ceils to whole kg; missing rate/COD card → 422, never a fallback.
- Seed demo data: `../.venv/bin/python scripts/seed.py` (idempotent) — admin `admin@lastmile-demo.com` / `Admin@123`. Don't use `.test`/`.local` emails in API payloads: pydantic EmailStr rejects reserved TLDs.
- Alembic note: autogenerate spuriously reports `ck_users_role` as removed on users table — ignore/strip that from new migrations.
- Admin CRUD endpoints live in one router (`app/routers/admin.py`, role-gated at router level via `dependencies=[Depends(require_role(ADMIN))]`).
- Status changes go through `app/services/state_machine.py` (`ALLOWED_TRANSITIONS` + `AGENT_ALLOWED_EDGES`) and `order_service.update_status()` — never set `order.status` directly. Agents only get forward edges from `ASSIGNED`; admin override allows anything except no-ops (remarks required).
- `order_tracking` immutability is enforced by DB trigger `trg_order_tracking_immutable` (migration ee4a9f5b4650): UPDATE/DELETE raise. TRUNCATE still works, so tests are unaffected. FAILED→PENDING is reserved for the Phase 7 reschedule flow.
- Tests build schema via Alembic migrations (not `create_all`) and recreate `lastmile_delivery_test` per session — keep triggers/constraints in migrations, not just model metadata.
- Assignment lives in `app/services/assignment_service.py`: only AVAILABLE agents are eligible; auto-assign sorts by (pickup-zone match desc, Haversine distance to pickup coords asc, user_id) — deterministic; assignment flips agent to BUSY; reaching any terminal status releases the agent via `release_agent_if_idle` called inside `order_service.update_status`. Distance needs coordinates: areas carry lat/lng centroids (`seed.py`, `pricing_world`), stamped onto orders at creation by `_area_for_pincode`. Agents can't go OFFLINE with active orders.
- Failed deliveries: entering FAILED increments `orders.delivery_attempt` (inside `order_service.update_status`); FAILED→PENDING goes ONLY through `POST /admin/orders/{id}/reschedule` (`order_service.reschedule_order`: clears assignment, bumps scheduled date default tomorrow, tracking row; past date → 422) — the generic admin override rejects that edge with a pointer to the reschedule endpoint.

## Conventions (from spec — enforce in every phase)

- Business logic lives in `app/services/*`; routers only parse/auth/delegate. No logic in route bodies.
- All rates/COD surcharges come from DB tables (`rate_cards`, `cod_rates`) — never hardcode pricing.
- `order_tracking` is append-only; every status change inserts a row inside the same transaction as the order update.
- Roles verified server-side (`CUSTOMER`/`AGENT`/`ADMIN`) on every protected endpoint; frontend checks are UX only.
- Never commit `.env`; secrets only in `.env.example` placeholders.
