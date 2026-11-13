# Airport Ground Operations & Baggage Management System

FastAPI backend for coordinating airport ground operations: airports, terminals, flights, gates and
check-in counters, passengers, check-in and boarding passes, baggage lifecycle and screening, ground staff,
tasks, aircraft turnaround, equipment, incidents, delays, resource allocation, notifications, dashboards,
reports and audit logs.

**Stack:** Python 3.11–3.14 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 · **MySQL via PyMySQL** · Alembic ·
JWT (OAuth2 password flow + optional Google OAuth2) · Pytest · Docker · Redis (optional)

---

## 1. Quick start

### Option A: Docker (MySQL + API)
```bash
cp .env.example .env              # adjust SECRET_KEY etc.
docker compose up --build         # runs migrations + seeds demo data, API on :8000
docker compose --profile test run --rm tests     # run the test-suite against MySQL
docker compose --profile redis up                # optionally start Redis too
```

### Option B: Local
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # set MYSQL_* to your MySQL server

# create the database once (MySQL shell)
#   CREATE DATABASE airport_ground_ops CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
#   CREATE USER 'airport'@'%' IDENTIFIED BY 'airport';
#   GRANT ALL ON airport_ground_ops.* TO 'airport'@'%';

alembic upgrade head            # create tables
python -m app.db.seed           # optional synthetic demo data
uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs** (Swagger) or **/redoc**.

| Account | Password |
|---|---|
| `admin@airportops.com` (SUPER_ADMIN, created at startup) | `Admin@12345` |
| `<role>@airportops.com` after seeding, e.g. `gate_agent@airportops.com` | `Passw0rd!` |

---

## 2. Authentication (OAuth2 + JWT)

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/auth/register` | Self-registration (JSON). Privileged roles (SUPER_ADMIN, OPS MANAGER) can only be created by an admin via `POST /users` |
| `POST /api/v1/auth/token` | **OAuth2 password flow** (form data `username` + `password`). Used by Swagger's **Authorize** button |
| `POST /api/v1/auth/login` | Same, with a JSON body |
| `POST /api/v1/auth/refresh` | New access token from a refresh token |
| `GET/PATCH /api/v1/auth/me` | Current user |
| `POST /api/v1/auth/change-password` · `forgot-password` · `reset-password` | Password management (single-use, hashed, expiring reset tokens) |
| `POST /api/v1/auth/logout-all` | Revoke every token for the user |
| `GET /api/v1/auth/oauth/google/login` → `/callback` | **OAuth2 social sign-up/login**: first login registers the account (role `OAUTH_DEFAULT_ROLE`), later logins link to it |
| `/api/v1/users/*` | Admin: list, create, activate/deactivate, change role |

* Passwords are hashed with **bcrypt**. Policy: 8+ chars with upper, lower, digit and special character.
* Access tokens carry `sub`, `role`, `ver`. Changing a password, role or deactivating a user bumps
  `token_version`, so every existing token stops working.
* Google OAuth2: create an OAuth client in Google Cloud Console, set `GOOGLE_CLIENT_ID`,
  `GOOGLE_CLIENT_SECRET` and `GOOGLE_REDIRECT_URI`, then open the URL returned by `/auth/oauth/google/login`.
* `REGISTRATION_REQUIRES_APPROVAL=true` makes new accounts inactive until an admin activates them.

### Role permissions (summary; SUPER_ADMIN can do everything)

| Area | Write access |
|---|---|
| Airports, terminals | Ops Manager |
| Flights, gates, counters, delays | Ops Manager, Flight Ops Officer (+ Gate Agent: gate assign / flight status; Check-in Agent: counter assign) |
| Passengers, check-in | Ops Manager, Check-in Agent (+ Gate Agent: boarding, passengers) |
| Baggage registration / tracking / screening | Ops Manager, Check-in Agent, Baggage Handling Staff, Ground Staff Supervisor |
| Staff, tasks, turnaround | Ops Manager, Ground Staff Supervisor, Flight Ops Officer (+ Baggage/Maintenance staff: execute tasks) |
| Equipment & maintenance | Ops Manager, Ground Staff Supervisor, Maintenance Staff |
| Incidents | Anyone can report; Ops Manager / Supervisor / Flight Ops manage |
| Reports | Ops Manager, Flight Ops Officer, Ground Staff Supervisor |
| Audit logs, user admin | Ops Manager, Super Admin |

The full matrix is in `app/core/permissions.py`.

---

## 3. API map (`/api/v1`)

| Day | Module | Main endpoints |
|---|---|---|
| 1 | Airports | `POST/GET /airports` (search `q`, country, city, status), `/airports/code/{code}`, `PATCH /{id}/status` |
| 1 | Terminals | `POST/GET /terminals`, `GET /terminals/{id}/map` (gates + counters) |
| 1 | Flights | `POST/GET /flights` (filters, date range, sorting), `PATCH /{id}` (schedule, audited), `PATCH /{id}/status` |
| 1 | Gates / Counters | register, `/available?start_time&end_time`, `POST /{id}/assign`, `/assignments` history, release |
| 2 | Passengers | register (synthetic), search (name/email/ID/PNR), `/{id}/flights` mapping, `/{id}/history` |
| 2 | Check-in | `POST /checkin` → check-in + **boarding pass reference**, seat change, cancel, board |
| 2 | Baggage | register (auto/unique tag), `PATCH /{id}/status`, `/{id}/history`, `/track/{tag}` |
| 2 | Screening | `POST /baggage/{id}/screenings` (CLEARED/HOLD/REJECTED), `POST /baggage/screenings/{id}/release` |
| 3 | Ground staff | `/ground-staff` (department, skills, shift, supervisor, availability), `/{id}/team` |
| 3 | Attendance | `/attendance/{staff_id}/check-in`, `check-out`, `/mark` |
| 3 | Ground tasks | create/assign/start/complete/cancel, `/ground-tasks/my` |
| 3 | Turnaround | `POST /turnarounds` (9 activities auto-created), parking, start/complete/skip activity, `/workflow` |
| 3 | Equipment | `/equipment`, `/equipment-assignments`, `/equipment-maintenance` (+ `/due`) |
| 3 | Incidents | create, assign, status workflow with history |
| 4 | Delays | `POST /delays` (minutes **or** new departure time), `/delays/flight/{id}` (history & total) |
| 4 | Resources | `POST /resources/allocate` (GATE/COUNTER/STAFF/EQUIPMENT), `/availability`, `/allocations` history |
| 4 | Notifications | my notifications, unread count, read/unread, read-all, broadcast |
| 4 | Dashboard | `/dashboard/overview` (+ `/today`, `/flights`, `/resources`, `/baggage`, `/operations`) |
| 4 | Reports | `/reports/flights/daily`, `/flights/monthly-performance`, `/baggage/handling`, `/baggage/missing`, `/staff/performance`, `/equipment/utilization`, `/delays/analysis`, `/turnarounds`, and `POST /reports/{name}/export-async` |
| 5 | Audit | `/audit-logs` (filters), `/audit-logs/entity/{type}/{id}` |

All reports support `date_from`, `date_to`, `page`, `size`, `sort_by`, `sort_order`, `airport_id` and
`format=csv`.

---

## 4. Business rules implemented

* **Flight status machine:** `SCHEDULED → CHECK_IN_OPEN → BOARDING → DEPARTED → ARRIVED`, with `DELAYED`
  and `CANCELLED` branches (see `GET /flights/status-transitions`). DEPARTED/ARRIVED set actual times;
  DEPARTED/CANCELLED **release gates, counters, equipment and staff** automatically.
* **Gate/counter/equipment/staff conflicts:** time-window overlap checks on ACTIVE assignments plus
  `SELECT … FOR UPDATE` row locks so concurrent requests can't double-book. Re-assigning a flight's gate is a
  **gate change**: the old assignment is cancelled and a notification is sent.
* **Check-in:** flight must be CHECK_IN_OPEN or DELAYED, passenger must be booked, **no duplicate check-in**
  (service check + DB unique key), seat validated and auto-assigned, counter must be assigned to the flight.
  It issues a boarding pass `BP-<FLIGHT>-<YYYYMMDD>-<RANDOM>` with gate, group and boarding time.
* **Baggage:** unique tags (duplicates rejected), weight limits per category, validated lifecycle transitions,
  **every status change writes a timestamped history row**, screening required before SORTING, a bag on hold
  can't move until it is released. Missing and delayed bags trigger notifications.
* **Turnaround:** dependency-aware workflow (e.g. cleaning and refuelling after disembarkation, final
  inspection after cleaning, refuelling and loading). An activity that overruns its plan requires a
  `delay_reason`. Total duration and over-target minutes are calculated when it finishes.
* **Delays:** `calculate_delay()` derives minutes ↔ new departure time. Delays are cumulative, the flight's
  `estimated_departure` is updated and the status moves to DELAYED. Severity-based notifications are sent.
* **Staff availability:** inactive, ON_LEAVE and OFF_DUTY staff can't be assigned, and nobody runs two tasks at
  once.
* **Equipment:** must be available and not overdue for maintenance. Usage hours are tracked on release.
* **Transactions:** one session per request. Services commit once per use-case, and any error rolls the whole
  unit of work back.
* **Centralised errors:** every error returns
  `{"success": false, "error": {"code", "message", "details"}, "request_id"}` with an appropriate HTTP status.
* **Audit log:** user, action, entity type and id, timestamp, previous and new values (JSON), IP address and
  request id. It records logins, flight schedule and status changes, gate and counter assignments, check-ins,
  baggage status, task assignments, equipment allocation, delays, incident resolution and more.

All datetimes are stored as **naive UTC** (MySQL `DATETIME`). Timezone-aware inputs are converted automatically.

---

## 5. Tests
```bash
pytest                       # 102 tests; uses a temporary SQLite DB, no server needed
TEST_DATABASE_URL="mysql+pymysql://user:pw@localhost:3306/airport_test?charset=utf8mb4" pytest   # same suite on MySQL
pytest --cov=app             # coverage
```
* `tests/unit`: transitions, delay maths, seat allocation, weight limits, JWT/password and turnaround rules.
* `tests/integration`: API tests per module, plus **`test_end_to_end_demo.py`**, which runs the full mandatory
  demo flow.

## 6. Migrations
```bash
alembic upgrade head                              # apply
alembic revision --autogenerate -m "describe"     # after model changes
alembic downgrade -1
```

## 7. Postman
Import `postman/airport_ground_operations_collection.json`.
* **0. End-to-End Demo**: run it with the Collection Runner. It walks through the mandatory demo in order
  (34 requests, saving ids and tokens into collection variables). On a non-empty DB, change the
  `dep_code`/`arr_code` variables first.
* The other folders hold every endpoint, grouped by module.
* Regenerate after API changes: `python scripts/generate_postman.py`.

## 8. Mandatory demo flow
Admin Login → Register Airport → Create Terminal → Register Flight → Assign Gate → Register Passenger →
Complete Check-in → Boarding Pass Reference → Register Baggage → Screening → Track Baggage → Assign Ground Staff →
Turnaround Tasks → Allocate Equipment → Record Delay → Update Flight Status → Dashboard → Reports → Audit Logs

You can run it three ways: in Swagger, with the Postman demo folder, or with
`pytest tests/integration/test_end_to_end_demo.py -v`.

## 9. Project layout
```
app/
  api/v1/<module>/routes.py   HTTP layer (validation, RBAC dependencies)
  services/                   business rules, transactions, audit + notifications
  repositories/               data access (SQLAlchemy 2.0 select())
  models/ schemas/            ORM tables / Pydantic DTOs
  core/                       config, security, JWT, permissions, constants, exceptions
  middleware/                 request-id, access log, centralised error handler
  workers/                    notification dispatch (Redis pub/sub if configured), background CSV reports
  db/                         engine/session, init (super admin), seed (synthetic data)
  utils/                      enums, pagination, filters, CSV export, reference generators
alembic/                      migrations
tests/unit, tests/integration
postman/                      collection
```
