# 💰 Finance Tracker API

A clean, production-quality **FastAPI** backend for personal finance management.
Built with SQLAlchemy 2, JWT authentication, role-based access control, SQL-level analytics, CSV/JSON export, and a comprehensive test suite.

---

## 📦 Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (swappable to PostgreSQL / MySQL) |
| Auth | JWT via `python-jose` |
| Passwords | `bcrypt` (direct, no passlib) |
| Validation | Pydantic v2 |
| Testing | pytest + FastAPI TestClient |

---

## 🏗️ Project Structure

```
finance_tracker/
├── main.py                          # App entry point, middleware, exception handlers
├── requirements.txt
├── .env.example
├── pytest.ini
│
└── app/
    ├── api/
    │   └── v1/
    │       ├── router.py            # Assembles all endpoint groups
    │       └── endpoints/
    │           ├── auth.py          # Register & login
    │           ├── transactions.py  # CRUD + filters + analytics
    │           ├── users.py         # User profile + admin management
    │           ├── admin.py         # Seed demo data + system stats
    │           └── export.py        # CSV and JSON export
    │
    ├── core/
    │   ├── config.py                # All settings via pydantic-settings
    │   └── security.py              # JWT + bcrypt utilities
    │
    ├── db/
    │   └── database.py              # Engine, session, Base, updated_at hook
    │
    ├── models/
    │   ├── __init__.py              # Imports all models (required for metadata)
    │   ├── user.py                  # User ORM model + UserRole enum
    │   └── transaction.py           # Transaction ORM model + enums
    │
    ├── schemas/
    │   ├── user.py                  # Pydantic request/response schemas
    │   └── transaction.py           # Pydantic request/response schemas
    │
    ├── services/
    │   ├── user_service.py          # Business logic for users
    │   └── transaction_service.py   # Business logic + SQL-level analytics
    │
    └── utils/
        └── dependencies.py          # FastAPI auth + RBAC dependencies

tests/
└── test_api.py                      # 55+ tests covering all endpoints
```

---

## 🚀 Quickstart

### 1. Unzip and enter the project

```bash
cd finance_tracker_final
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it:
- **Windows**: `venv\Scripts\activate`
- **Mac/Linux**: `source venv/bin/activate`

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment (optional)

```bash
cp .env.example .env
# Edit .env to change SECRET_KEY or switch to PostgreSQL
```

### 5. Run the server

```bash
uvicorn main:app --reload
```

The API is now live at **http://127.0.0.1:8000**

---

## 📖 Interactive API Documentation

Once running, open your browser to:

| URL | Description |
|---|---|
| http://127.0.0.1:8000/docs | **Swagger UI** — try every endpoint interactively |
| http://127.0.0.1:8000/redoc | ReDoc — clean reference documentation |
| http://127.0.0.1:8000/health | Liveness probe |

---

## 🔐 Authentication Flow

1. **Register** → `POST /api/v1/auth/register`
2. **Login** → `POST /api/v1/auth/login` → receive `access_token`
3. **Authorize** → In Swagger UI click **"Authorize"**, enter `Bearer <your_token>`
4. All protected endpoints now work automatically

---

## 👥 Roles & Permissions

| Action | Viewer | Analyst | Admin |
|---|:---:|:---:|:---:|
| View own transactions | ✅ | ✅ | ✅ |
| View summaries / analytics | ✅ | ✅ | ✅ |
| Export to CSV / JSON | ✅ | ✅ | ✅ |
| Create transactions | ❌ | ✅ | ✅ |
| Update transactions | ❌ | ✅ | ✅ |
| Delete transactions | ❌ | ❌ | ✅ |
| View all users' transactions | ❌ | ❌ | ✅ |
| Manage users | ❌ | ❌ | ✅ |
| Seed demo data | ❌ | ❌ | ✅ |

---

## 🌱 Demo Data (Recommended for Evaluation)

To quickly populate the database with realistic test data:

**Step 1** — Register an admin account:
```json
POST /api/v1/auth/register
{
  "full_name": "Super Admin",
  "email": "super@admin.com",
  "password": "Admin1234",
  "role": "admin"
}
```

**Step 2** — Login and copy the `access_token`.

**Step 3** — Authorize in Swagger (click **Authorize**, paste `Bearer <token>`).

**Step 4** — Call the seed endpoint:
```
POST /api/v1/admin/seed
```

This creates 3 demo users with ~120 transactions across the last 12 months.

| Email | Password | Role |
|---|---|---|
| viewer@demo.com | Viewer123 | viewer |
| analyst@demo.com | Analyst123 | analyst |
| admin@demo.com | Admin1234 | admin |

---

## 📊 API Endpoints

### Authentication
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login, receive JWT token |

### Transactions
| Method | Path | Access | Description |
|---|---|---|---|
| POST | `/api/v1/transactions/` | Analyst, Admin | Create transaction |
| GET | `/api/v1/transactions/` | All | List with filters + pagination |
| GET | `/api/v1/transactions/summary` | All | Full analytics summary |
| GET | `/api/v1/transactions/{id}` | All | Get single transaction |
| PATCH | `/api/v1/transactions/{id}` | Analyst, Admin | Partial update |
| DELETE | `/api/v1/transactions/{id}` | Admin | Delete transaction |

### Filter Parameters (`GET /transactions/`)
| Param | Type | Example |
|---|---|---|
| `type` | `income` \| `expense` | `?type=expense` |
| `category` | Category enum | `?category=food` |
| `start_date` | YYYY-MM-DD | `?start_date=2024-01-01` |
| `end_date` | YYYY-MM-DD | `?end_date=2024-12-31` |
| `min_amount` | float | `?min_amount=100` |
| `max_amount` | float | `?max_amount=5000` |
| `search` | string | `?search=grocery` |
| `page` | int | `?page=2` |
| `page_size` | int (max 100) | `?page_size=10` |

### Users
| Method | Path | Access | Description |
|---|---|---|---|
| GET | `/api/v1/users/me` | All | Your profile |
| PATCH | `/api/v1/users/me/password` | All | Change your password |
| GET | `/api/v1/users/` | Admin | List all users |
| GET | `/api/v1/users/{id}` | Admin | Get user by ID |
| PATCH | `/api/v1/users/{id}` | Admin | Update user |
| DELETE | `/api/v1/users/{id}` | Admin | Delete user |

### Admin
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/admin/seed` | Seed demo data |
| GET | `/api/v1/admin/stats` | System-wide statistics |

### Export
| Method | Path | Access | Description |
|---|---|---|---|
| GET | `/api/v1/export/csv` | All | Download transactions as CSV file |
| GET | `/api/v1/export/json` | All | Download transactions as JSON file |

Both export endpoints support the same `start_date`, `end_date`, `type`, and `category` filters as the main listing endpoint.

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

Expected output: **55+ tests passing**, covering:
- Auth: register, login, validation, duplicate email, token expiry
- Transactions: CRUD, role enforcement, all filter combinations, pagination, user isolation
- Analytics: summary correctness, category percentages, monthly splits, admin vs user scope
- Users: profile, admin management, password change, self-delete prevention
- Export: CSV structure, JSON structure, empty results, auth required
- Health: root and health check endpoints

---

## 📋 Transaction Categories

**Income:** `salary`, `freelance`, `investment`, `gift`, `other_income`

**Expense:** `food`, `housing`, `transport`, `healthcare`, `education`, `entertainment`, `shopping`, `utilities`, `travel`, `other_expense`

---

## 🔢 Validation Rules

- **Amount**: must be > 0 and ≤ 10,000,000; stored as `Numeric(15,2)` (exact, no float drift)
- **Date**: cannot be in the future
- **Description**: optional, max 500 characters, whitespace-trimmed
- **TransactionUpdate**: empty body `{}` is rejected (at least one field required)
- **Password**: min 8 chars, must include at least one letter and one digit
- **Email**: must be a valid, unique email; stored and matched in lowercase

---

## 💡 Design Decisions

### 1. Service Layer Pattern
Route handlers are thin — all business logic lives in `services/`. This makes code testable and easy to extend without touching routes.

### 2. SQL-Level Analytics
`get_summary()` uses `func.sum()`, `func.avg()`, `func.max()` with SQLAlchemy `case()` expressions. The entire summary is computed in **one SQL query** rather than loading all transactions into Python memory. This scales to millions of records.

### 3. Exact Money Storage
`Column(Numeric(precision=15, scale=2))` prevents the classic float rounding bug where `5000.1 + 100.3 == 5100.399999...`. All amounts are stored and returned as exact decimals.

### 4. Reliable `updated_at`
SQLAlchemy's `onupdate=` keyword doesn't fire for in-process attribute changes. Instead, a `before_flush` session event listener in `database.py` auto-sets `updated_at` on every dirty object — works correctly for all update paths.

### 5. Route Ordering
`GET /transactions/summary` is declared **before** `GET /transactions/{id}`. FastAPI matches routes top-to-bottom, so without this ordering, the word "summary" would be cast to an integer and return a 422 error.

### 6. Global Exception Handlers
Three handlers in `main.py` ensure:
- HTTP errors always return `{"detail": "..."}` JSON (not HTML)
- Validation errors return a clean flat list of `{field, message, type}` objects
- Unhandled exceptions return a safe 500 message without leaking stack traces

### 7. Direct bcrypt (No passlib)
`passlib==1.7.4` is incompatible with `bcrypt>=4.0` because the newer bcrypt removed the `__about__` module that passlib reads for version detection. This project uses `bcrypt` directly to avoid this crash entirely.

### 8. SQLite by Default
Zero external dependencies for evaluation. Swap `DATABASE_URL` in `.env` for PostgreSQL or MySQL — no code changes needed.

---

## 🗃️ Switching to PostgreSQL

1. Install the driver:
   ```bash
   pip install psycopg2-binary
   ```
2. Update `.env`:
   ```
   DATABASE_URL=postgresql://user:password@localhost:5432/finance_tracker
   ```
3. Restart the server — SQLAlchemy and the app handle the rest automatically.

---

## 🔒 Assumptions Made

1. **Role self-assignment on registration** is permitted for evaluation convenience. In production this would be restricted so only admins can grant `admin` or `analyst` roles.
2. **Token invalidation on logout** is not implemented (stateless JWT). A production system would use a token blocklist or short-lived tokens with refresh tokens.
3. **Rate limiting** is not applied. A production deployment would add this at the reverse proxy (nginx/Caddy) or via a middleware library.