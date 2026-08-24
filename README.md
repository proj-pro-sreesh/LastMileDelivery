# Last-Mile Delivery Tracker

Delivery management platform for last-mile logistics: customers create delivery orders, admins configure zones/rates and manage agents, delivery agents execute deliveries — with automatic pricing (volumetric weight, B2B/B2C, intra/inter-zone, COD surcharge), nearest-agent assignment, immutable tracking history, failed-delivery rescheduling, and notifications.

**Stack:** FastAPI · SQLAlchemy · Alembic · PostgreSQL · Next.js · TypeScript · Tailwind CSS

> README is being expanded as implementation phases land. Full setup/deployment docs arrive with the final phase; see `docs/` when populated.

## Quick start (developer)

Backend (Python 3.14 venv at repo root):

```bash
createdb lastmile_delivery            # once
cd backend && ../.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                  # then adjust DATABASE_URL if needed
../.venv/bin/alembic upgrade head
../.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Frontend (Phase 9).

## Tests

```bash
cd .. && .venv/bin/python -m pytest backend/tests -q
```
