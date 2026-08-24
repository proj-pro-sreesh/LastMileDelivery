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
- `backend/tests/conftest.py` puts `backend/` on `sys.path` so pytest works from repo root.

## Conventions (from spec — enforce in every phase)

- Business logic lives in `app/services/*`; routers only parse/auth/delegate. No logic in route bodies.
- All rates/COD surcharges come from DB tables (`rate_cards`, `cod_rates`) — never hardcode pricing.
- `order_tracking` is append-only; every status change inserts a row inside the same transaction as the order update.
- Roles verified server-side (`CUSTOMER`/`AGENT`/`ADMIN`) on every protected endpoint; frontend checks are UX only.
- Never commit `.env`; secrets only in `.env.example` placeholders.
