"""
Comprehensive test suite for the Finance Tracker API.

Tests cover:
- Authentication (register, login, token validation)
- Transaction CRUD with role-based access control
- Financial analytics/summary endpoint
- Export endpoints (CSV, JSON)
- Validation and error handling
- Pagination and filtering

Run with: pytest tests/ -v
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from app.db.database import Base, get_db
from app.models.user import User, UserRole
from app.models.transaction import Transaction, TransactionType, Category
from app.core.security import hash_password

# ── In-memory SQLite test database ──────────────────────────────────────────
TEST_DATABASE_URL = "sqlite:///./test_finance_tracker.db"

engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


# ── Helper factories ─────────────────────────────────────────────────────────

def create_user_directly(role: UserRole = UserRole.VIEWER, email: str = "test@example.com"):
    """Insert a user directly into the DB (bypasses API)."""
    db = TestingSessionLocal()
    user = User(
        full_name="Test User",
        email=email,
        hashed_password=hash_password("TestPass1"),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def get_token(client: TestClient, email: str = "test@example.com", password: str = "TestPass1") -> str:
    """Login and return bearer token."""
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def create_transaction_via_api(client, token, **kwargs) -> dict:
    defaults = {
        "amount": 1000.00,
        "type": "income",
        "category": "salary",
        "description": "Test transaction",
        "date": str(date.today()),
    }
    defaults.update(kwargs)
    resp = client.post("/api/v1/transactions/", json=defaults, headers=auth_headers(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


# ═══════════════════════════════════════════════════════════════════════════
# AUTHENTICATION TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestRegister:
    def test_register_success(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "full_name": "Alice Johnson",
            "email": "alice@example.com",
            "password": "SecurePass1",
            "role": "viewer",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "alice@example.com"
        assert data["role"] == "viewer"
        assert "hashed_password" not in data  # never leaked

    def test_register_duplicate_email(self, client):
        payload = {"full_name": "Alice", "email": "alice@example.com",
                   "password": "SecurePass1", "role": "viewer"}
        client.post("/api/v1/auth/register", json=payload)
        resp = client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 409

    def test_register_weak_password(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "full_name": "Bob", "email": "bob@example.com",
            "password": "short",  # too short
            "role": "viewer",
        })
        assert resp.status_code == 422

    def test_register_password_no_digit(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "full_name": "Bob", "email": "bob@example.com",
            "password": "NoDigitHere",
            "role": "viewer",
        })
        assert resp.status_code == 422

    def test_register_invalid_email(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "full_name": "Bob", "email": "not-an-email",
            "password": "ValidPass1", "role": "viewer",
        })
        assert resp.status_code == 422

    def test_register_short_name(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "full_name": "A", "email": "a@example.com",
            "password": "ValidPass1", "role": "viewer",
        })
        assert resp.status_code == 422

    def test_register_default_role_is_viewer(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "full_name": "Charlie", "email": "charlie@example.com",
            "password": "ValidPass1",
        })
        assert resp.status_code == 201
        assert resp.json()["role"] == "viewer"


class TestLogin:
    def test_login_success(self, client):
        client.post("/api/v1/auth/register", json={
            "full_name": "Alice", "email": "alice@example.com",
            "password": "SecurePass1", "role": "viewer",
        })
        resp = client.post("/api/v1/auth/login", json={
            "email": "alice@example.com", "password": "SecurePass1"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "alice@example.com"

    def test_login_wrong_password(self, client):
        client.post("/api/v1/auth/register", json={
            "full_name": "Alice", "email": "alice@example.com",
            "password": "SecurePass1", "role": "viewer",
        })
        resp = client.post("/api/v1/auth/login", json={
            "email": "alice@example.com", "password": "WrongPass1"
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com", "password": "ValidPass1"
        })
        assert resp.status_code == 401

    def test_no_token_returns_403(self, client):
        resp = client.get("/api/v1/users/me")
        assert resp.status_code in (401, 403)

    def test_invalid_token_returns_401(self, client):
        resp = client.get("/api/v1/users/me",
                          headers={"Authorization": "Bearer invalidtoken"})
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# USER PROFILE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestUserProfile:
    def test_get_own_profile(self, client):
        create_user_directly(UserRole.VIEWER, "me@example.com")
        token = get_token(client, "me@example.com")
        resp = client.get("/api/v1/users/me", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["email"] == "me@example.com"

    def test_change_password_success(self, client):
        create_user_directly(UserRole.VIEWER, "user@example.com")
        token = get_token(client, "user@example.com")
        resp = client.patch("/api/v1/users/me/password", headers=auth_headers(token), json={
            "current_password": "TestPass1",
            "new_password": "NewPass99",
        })
        assert resp.status_code == 200
        # Should now be able to login with new password
        resp2 = client.post("/api/v1/auth/login", json={
            "email": "user@example.com", "password": "NewPass99"
        })
        assert resp2.status_code == 200

    def test_change_password_wrong_current(self, client):
        create_user_directly(UserRole.VIEWER, "user@example.com")
        token = get_token(client, "user@example.com")
        resp = client.patch("/api/v1/users/me/password", headers=auth_headers(token), json={
            "current_password": "WrongPass1",
            "new_password": "NewPass99",
        })
        assert resp.status_code == 401

    def test_change_password_same_as_current(self, client):
        create_user_directly(UserRole.VIEWER, "user@example.com")
        token = get_token(client, "user@example.com")
        resp = client.patch("/api/v1/users/me/password", headers=auth_headers(token), json={
            "current_password": "TestPass1",
            "new_password": "TestPass1",  # same!
        })
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# TRANSACTION CRUD TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestTransactionCreate:
    def test_analyst_can_create(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        resp = client.post("/api/v1/transactions/", headers=auth_headers(token), json={
            "amount": 5000.00,
            "type": "income",
            "category": "salary",
            "description": "Monthly salary",
            "date": str(date.today()),
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["amount"] == "5000.00"
        assert data["type"] == "income"
        assert data["category"] == "salary"

    def test_viewer_cannot_create(self, client):
        create_user_directly(UserRole.VIEWER, "viewer@example.com")
        token = get_token(client, "viewer@example.com")
        resp = client.post("/api/v1/transactions/", headers=auth_headers(token), json={
            "amount": 100.00, "type": "expense", "category": "food",
            "date": str(date.today()),
        })
        assert resp.status_code == 403

    def test_negative_amount_rejected(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        resp = client.post("/api/v1/transactions/", headers=auth_headers(token), json={
            "amount": -100, "type": "expense", "category": "food",
            "date": str(date.today()),
        })
        assert resp.status_code == 422

    def test_zero_amount_rejected(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        resp = client.post("/api/v1/transactions/", headers=auth_headers(token), json={
            "amount": 0, "type": "expense", "category": "food",
            "date": str(date.today()),
        })
        assert resp.status_code == 422

    def test_future_date_rejected(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        future = (date.today() + timedelta(days=10)).isoformat()
        resp = client.post("/api/v1/transactions/", headers=auth_headers(token), json={
            "amount": 100, "type": "expense", "category": "food",
            "date": future,
        })
        assert resp.status_code == 422

    def test_invalid_category_rejected(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        resp = client.post("/api/v1/transactions/", headers=auth_headers(token), json={
            "amount": 100, "type": "expense", "category": "NONEXISTENT",
            "date": str(date.today()),
        })
        assert resp.status_code == 422


class TestTransactionRead:
    def test_list_own_transactions(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        create_transaction_via_api(client, token)
        create_transaction_via_api(client, token, amount=200, type="expense", category="food")

        resp = client.get("/api/v1/transactions/", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_viewer_can_list(self, client):
        create_user_directly(UserRole.VIEWER, "viewer@example.com")
        token = get_token(client, "viewer@example.com")
        resp = client.get("/api/v1/transactions/", headers=auth_headers(token))
        assert resp.status_code == 200

    def test_user_cannot_see_others_transactions(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        create_user_directly(UserRole.ANALYST, "other@example.com")
        token_a = get_token(client, "analyst@example.com")
        token_b = get_token(client, "other@example.com")

        create_transaction_via_api(client, token_a)  # created by user A
        resp = client.get("/api/v1/transactions/", headers=auth_headers(token_b))
        assert resp.json()["total"] == 0  # user B sees nothing

    def test_get_single_transaction(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        tx = create_transaction_via_api(client, token)
        resp = client.get(f"/api/v1/transactions/{tx['id']}", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["id"] == tx["id"]

    def test_get_nonexistent_transaction(self, client):
        create_user_directly(UserRole.VIEWER, "viewer@example.com")
        token = get_token(client, "viewer@example.com")
        resp = client.get("/api/v1/transactions/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    def test_filter_by_type(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        create_transaction_via_api(client, token, type="income", category="salary")
        create_transaction_via_api(client, token, type="expense", category="food")

        resp = client.get("/api/v1/transactions/?type=income", headers=auth_headers(token))
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["type"] == "income"

    def test_pagination(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        for i in range(5):
            create_transaction_via_api(client, token)

        resp = client.get("/api/v1/transactions/?page=1&page_size=2", headers=auth_headers(token))
        data = resp.json()
        assert data["total"] == 5
        assert data["total_pages"] == 3
        assert len(data["items"]) == 2

    def test_search_by_description(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        create_transaction_via_api(client, token, description="Monthly salary payment")
        create_transaction_via_api(client, token, description="Grocery shopping")

        resp = client.get("/api/v1/transactions/?search=salary", headers=auth_headers(token))
        assert resp.json()["total"] == 1


class TestTransactionUpdate:
    def test_analyst_can_update(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        tx = create_transaction_via_api(client, token)
        resp = client.patch(f"/api/v1/transactions/{tx['id']}",
                            headers=auth_headers(token),
                            json={"amount": 9999.00})
        assert resp.status_code == 200
        assert resp.json()["amount"] == "9999.00"

    def test_viewer_cannot_update(self, client):
        # Create tx as admin, then try to update as viewer
        create_user_directly(UserRole.ADMIN, "admin@example.com")
        create_user_directly(UserRole.VIEWER, "viewer@example.com")
        admin_token = get_token(client, "admin@example.com")
        viewer_token = get_token(client, "viewer@example.com")
        tx = create_transaction_via_api(client, admin_token)

        resp = client.patch(f"/api/v1/transactions/{tx['id']}",
                            headers=auth_headers(viewer_token),
                            json={"amount": 999.00})
        assert resp.status_code == 403

    def test_empty_update_body_rejected(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        tx = create_transaction_via_api(client, token)
        resp = client.patch(f"/api/v1/transactions/{tx['id']}",
                            headers=auth_headers(token),
                            json={})
        assert resp.status_code == 422


class TestTransactionDelete:
    def test_admin_can_delete(self, client):
        create_user_directly(UserRole.ADMIN, "admin@example.com")
        token = get_token(client, "admin@example.com")
        tx = create_transaction_via_api(client, token)
        resp = client.delete(f"/api/v1/transactions/{tx['id']}", headers=auth_headers(token))
        assert resp.status_code == 204

    def test_analyst_cannot_delete(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        tx = create_transaction_via_api(client, token)
        resp = client.delete(f"/api/v1/transactions/{tx['id']}", headers=auth_headers(token))
        assert resp.status_code == 403

    def test_delete_nonexistent_returns_404(self, client):
        create_user_directly(UserRole.ADMIN, "admin@example.com")
        token = get_token(client, "admin@example.com")
        resp = client.delete("/api/v1/transactions/99999", headers=auth_headers(token))
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# ANALYTICS SUMMARY TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestSummary:
    def test_summary_empty(self, client):
        create_user_directly(UserRole.VIEWER, "viewer@example.com")
        token = get_token(client, "viewer@example.com")
        resp = client.get("/api/v1/transactions/summary", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_income"] == 0.0
        assert data["total_expenses"] == 0.0
        assert data["current_balance"] == 0.0

    def test_summary_with_transactions(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        create_transaction_via_api(client, token, amount=5000, type="income", category="salary")
        create_transaction_via_api(client, token, amount=1000, type="expense", category="food")

        resp = client.get("/api/v1/transactions/summary", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_income"] == 5000.0
        assert data["total_expenses"] == 1000.0
        assert data["current_balance"] == 4000.0
        assert data["transaction_count"] == 2
        assert len(data["category_breakdown"]) == 2
        assert len(data["recent_transactions"]) == 2

    def test_admin_sees_all_in_summary(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        create_user_directly(UserRole.ADMIN, "admin@example.com")
        analyst_token = get_token(client, "analyst@example.com")
        admin_token = get_token(client, "admin@example.com")

        create_transaction_via_api(client, analyst_token, amount=1000)
        create_transaction_via_api(client, admin_token, amount=2000)

        resp = client.get("/api/v1/transactions/summary", headers=auth_headers(admin_token))
        assert resp.json()["total_income"] == 3000.0


# ═══════════════════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestAdminEndpoints:
    def test_seed_creates_users_and_transactions(self, client):
        create_user_directly(UserRole.ADMIN, "admin@example.com")
        token = get_token(client, "admin@example.com")
        resp = client.post("/api/v1/admin/seed", headers=auth_headers(token))
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["new_users_created"]) == 3
        assert data["transactions_created"] > 0

    def test_seed_is_idempotent(self, client):
        create_user_directly(UserRole.ADMIN, "admin@example.com")
        token = get_token(client, "admin@example.com")
        client.post("/api/v1/admin/seed", headers=auth_headers(token))
        resp2 = client.post("/api/v1/admin/seed", headers=auth_headers(token))
        assert resp2.status_code == 201
        assert resp2.json()["new_users_created"] == []  # no new users on second run

    def test_non_admin_cannot_seed(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        resp = client.post("/api/v1/admin/seed", headers=auth_headers(token))
        assert resp.status_code == 403

    def test_system_stats(self, client):
        create_user_directly(UserRole.ADMIN, "admin@example.com")
        token = get_token(client, "admin@example.com")
        resp = client.get("/api/v1/admin/stats", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "transactions" in data

    def test_list_users_admin_only(self, client):
        create_user_directly(UserRole.ADMIN, "admin@example.com")
        create_user_directly(UserRole.VIEWER, "viewer@example.com")
        admin_token = get_token(client, "admin@example.com")
        viewer_token = get_token(client, "viewer@example.com")

        # Admin can list
        resp = client.get("/api/v1/users/", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        # Viewer cannot
        resp2 = client.get("/api/v1/users/", headers=auth_headers(viewer_token))
        assert resp2.status_code == 403

    def test_admin_cannot_delete_self(self, client):
        create_user_directly(UserRole.ADMIN, "admin@example.com")
        token = get_token(client, "admin@example.com")
        # get own id
        me = client.get("/api/v1/users/me", headers=auth_headers(token)).json()
        resp = client.delete(f"/api/v1/users/{me['id']}", headers=auth_headers(token))
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# EXPORT TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestExport:
    def test_csv_export(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        create_transaction_via_api(client, token)
        create_transaction_via_api(client, token, amount=500, type="expense", category="food")

        resp = client.get("/api/v1/export/csv", headers=auth_headers(token))
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        content = resp.text
        assert "id,date,type,category,amount" in content
        assert "salary" in content
        assert "food" in content

    def test_json_export(self, client):
        create_user_directly(UserRole.ANALYST, "analyst@example.com")
        token = get_token(client, "analyst@example.com")
        create_transaction_via_api(client, token)

        resp = client.get("/api/v1/export/json", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "transactions" in data
        assert data["total"] == 1
        assert data["transactions"][0]["type"] == "income"

    def test_export_empty_returns_valid_structure(self, client):
        create_user_directly(UserRole.VIEWER, "viewer@example.com")
        token = get_token(client, "viewer@example.com")
        resp = client.get("/api/v1/export/csv", headers=auth_headers(token))
        assert resp.status_code == 200
        # Should have header row but no data rows
        lines = [l for l in resp.text.strip().split("\n") if l]
        assert len(lines) == 1  # only the header

    def test_export_requires_auth(self, client):
        resp = client.get("/api/v1/export/csv")
        assert resp.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════════
# HEALTH & ROOT TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestHealthEndpoints:
    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"