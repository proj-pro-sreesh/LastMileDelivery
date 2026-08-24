# System Design — Last-Mile Delivery Tracker

## Overview

A two-sided shipment tracker: customers book parcels and follow them; admins manage pricing
geography and operations; agents execute deliveries. The backend is FastAPI + SQLAlchemy on
PostgreSQL; the frontend is Next.js (App Router) + TypeScript + Tailwind. Business rules live in
`app/services/*` — routers only parse input, authenticate, delegate, and map domain errors to HTTP
codes.

## Zone detection & pricing

Geography is three tables: `zones → areas → pincodes`. Each pincode belongs to exactly one area
(`areas.pincode` UNIQUE), each area to one zone. Given a pickup/drop pincode, `zone_service`
resolves the chain; an unmapped pincode raises immediately and surfaces as **422** — there is no
fallback pricing anywhere.

`rate_engine.calculate_quote()` is the single source of truth for money. Both the quote endpoint
and order creation call it, so a customer can never book at a price other than the quoted one.
The engine:

1. Resolves both zones from pincodes.
2. Classifies the lane: same zone (`from = to`) → *intra-zone*, else *inter-zone*. Intra-zone rates
   are stored as rate-card rows whose `from_zone_id = to_zone_id`.
3. Computes chargeable weight:
   - `volumetric_weight_kg = L × B × H / 5000`
   - `chargeable_weight_kg = ceil(max(actual, volumetric))` to whole kilograms.
4. Looks up the rate card by `(order_type B2B|B2C, from_zone, to_zone)`; missing card → 422.
5. `base_charge = max(rate_per_kg × chargeable_weight, minimum_charge)`.
6. COD payment adds the surcharge from `cod_rates` keyed by order type; missing row → 422.
7. `total_charge = base_charge + cod_surcharge`, stamped immutably onto the order.

All numbers come from DB tables — no hardcoded prices exist in code.

## Order lifecycle & audit trail

Statuses: `PENDING → ASSIGNED → PICKED_UP → IN_TRANSIT → OUT_FOR_DELIVERY → DELIVERED`, with
`FAILED` (delivery attempt failed), `CANCELLED`, and reschedule-driven returns to `PENDING`.
Every change goes through `order_service.update_status()`, which consults
`state_machine.ALLOWED_TRANSITIONS`; agents are further restricted to forward edges from their
assigned orders (`AGENT_ALLOWED_EDGES`). Admins may override any transition except no-ops, and a
remarks field is mandatory for overrides — the remarks land in the timeline. The generic override
rejects `FAILED → PENDING` with a pointer to the dedicated reschedule endpoint, keeping one
audited path for redeliveries.

Each transition writes an append-only `order_tracking` row inside the same transaction as the
order update. Immutability is enforced by a database trigger (`trg_order_tracking_immutable`) that
raises on UPDATE/DELETE, so even raw SQL cannot rewrite history.

## Auto-assignment

Orders carry pickup coordinates (area centroids, stamped at creation). `assignment_service.auto_assign`
scores every AVAILABLE agent:

1. **Zone match** — agents whose `current_zone_id` equals the pickup zone sort first.
2. **Distance** — Haversine distance between agent location and pickup centroid, ascending;
   agents without coordinates sort last.
3. **Determinism** — ties break by `user_id`, so repeated runs pick the same agent.

Assignment flips the agent to BUSY and notifies both parties. Reaching a terminal status
(`DELIVERED`, `FAILED`, `CANCELLED`) releases the agent inside the same transaction. Agents cannot
go OFFLINE while holding active orders. Admins can also assign manually (same eligibility rules)
or trigger auto-assign per order.

## Failed deliveries & rescheduling

Marking an attempt FAILED increments `orders.delivery_attempt`. Recovery happens only through the
reschedule flow (`POST /orders/{id}/reschedule` for owners, `/admin/orders/{id}/reschedule` for
admins): status returns to PENDING, the old assignment clears and the agent is released, the new
date defaults to tomorrow (past dates → 422), a `reschedules` audit row records who/when/from/to,
the tracking history gets its immutable entry, and the customer is notified. Customer-initiated
redeliveries open a fresh delivery attempt and immediately re-enter the auto-assignment queue; if
no agent is available the order simply waits as PENDING.

## Notifications

`notification_service` writes in-app rows and dispatches email/SMS through swappable providers
(mock logger, Resend, Twilio). Persistence runs in a SAVEPOINT and outbound sends are individually
failure-isolated, so a dead SMTP provider degrades to log noise instead of rolling back an order
transaction. `NOTIFICATIONS_MODE=disabled` silences everything. Recipients poll
`GET /notifications`; read state is owner-scoped.

## API & security

JWT bearer tokens (24 h expiry); passwords hashed with bcrypt. Role checks run server-side on
every protected route via `require_role(...)` dependencies; the frontend's role gating is UX only.
Customers see only their orders (ownership violations look like 404s — no enumeration); agents see
only assigned orders; admins see everything plus operational filters (status, pickup-or-drop zone,
assigned agent). Emails are lowercased at registration; duplicate signup and bad login return
uniform errors.

## Deployment

Docker Compose runs Postgres 18, an API container that migrates on boot, and the frontend. A
Render Blueprint (`render.yaml`) provisions the managed database + API with automatic Alembic
migrations; the frontend deploys to Vercel with `NEXT_PUBLIC_API_URL` baked at build time.
