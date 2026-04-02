"""
Admin utility endpoints — seed demo data and system statistics.
All routes require Admin role.
"""

from datetime import date, timedelta
import random

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.transaction import Transaction, TransactionType, Category
from app.core.security import hash_password
from app.utils.dependencies import require_admin

router = APIRouter()


INCOME_CATEGORIES = [
    Category.SALARY, Category.FREELANCE, Category.INVESTMENT, Category.GIFT,
]
EXPENSE_CATEGORIES = [
    Category.FOOD, Category.HOUSING, Category.TRANSPORT, Category.HEALTHCARE,
    Category.ENTERTAINMENT, Category.SHOPPING, Category.UTILITIES, Category.TRAVEL,
]

INCOME_DESCRIPTIONS = [
    "Monthly salary", "Freelance project payment", "Stock dividend",
    "Birthday gift", "Bonus payment", "Side project income", "Consulting fee",
    "Investment returns", "Rental income", "Online course revenue",
]
EXPENSE_DESCRIPTIONS = [
    "Grocery shopping", "Electricity bill", "Netflix subscription",
    "Bus pass", "Doctor visit", "Online course", "Restaurant dinner",
    "Flight tickets", "New shoes", "Internet bill", "Gym membership",
    "Coffee shop", "Car maintenance", "Home repair", "Pharmacy",
]


@router.post(
    "/seed",
    summary="Seed demo data (admin)",
    status_code=201,
    responses={
        201: {"description": "Demo data seeded successfully"},
        403: {"description": "Admin role required"},
    },
)
def seed_demo_data(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Populate the database with realistic demo users and transactions.

    **Creates:**
    - 3 demo users: viewer, analyst, admin
    - ~120 transactions spread across the last 12 months

    **Idempotent** — safe to call multiple times.
    Skips creation if demo users or their transactions already exist.
    """
    created_users = []
    created_transactions = 0

    demo_accounts = [
        {
            "full_name": "Demo Viewer",
            "email": "viewer@demo.com",
            "password": "Viewer123",
            "role": UserRole.VIEWER,
        },
        {
            "full_name": "Demo Analyst",
            "email": "analyst@demo.com",
            "password": "Analyst123",
            "role": UserRole.ANALYST,
        },
        {
            "full_name": "Demo Admin",
            "email": "admin@demo.com",
            "password": "Admin1234",
            "role": UserRole.ADMIN,
        },
    ]

    users_to_seed: list[User] = []
    for account in demo_accounts:
        existing = db.query(User).filter(User.email == account["email"]).first()
        if not existing:
            user = User(
                full_name=account["full_name"],
                email=account["email"],
                hashed_password=hash_password(account["password"]),
                role=account["role"],
            )
            db.add(user)
            db.flush()
            created_users.append(account["email"])
            users_to_seed.append(user)
        else:
            users_to_seed.append(existing)

    db.commit()

    # Generate transactions for each demo user
    today = date.today()
    rng = random.Random(42)  # Deterministic seed for reproducibility

    for user in users_to_seed:
        existing_count = (
            db.query(Transaction).filter(Transaction.user_id == user.id).count()
        )
        if existing_count > 0:
            continue

        for _ in range(40):
            days_ago = rng.randint(0, 365)
            tx_date = today - timedelta(days=days_ago)

            is_income = rng.random() < 0.3  # ~30% income, 70% expense
            tx_type = TransactionType.INCOME if is_income else TransactionType.EXPENSE

            if is_income:
                amount = round(rng.uniform(500, 8000), 2)
                category = rng.choice(INCOME_CATEGORIES)
                description = rng.choice(INCOME_DESCRIPTIONS)
            else:
                amount = round(rng.uniform(10, 1500), 2)
                category = rng.choice(EXPENSE_CATEGORIES)
                description = rng.choice(EXPENSE_DESCRIPTIONS)

            tx = Transaction(
                amount=amount,
                type=tx_type,
                category=category,
                description=description,
                date=tx_date,
                user_id=user.id,
            )
            db.add(tx)
            created_transactions += 1

    db.commit()

    return {
        "message": "Demo data seeded successfully.",
        "new_users_created": created_users,
        "transactions_created": created_transactions,
        "demo_credentials": [
            {"email": "viewer@demo.com", "password": "Viewer123", "role": "viewer"},
            {"email": "analyst@demo.com", "password": "Analyst123", "role": "analyst"},
            {"email": "admin@demo.com", "password": "Admin1234", "role": "admin"},
        ],
    }


@router.get(
    "/stats",
    summary="System-wide statistics (admin)",
    responses={
        200: {"description": "System statistics"},
        403: {"description": "Admin role required"},
    },
)
def system_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Get high-level system-wide statistics.

    **Requires**: Admin role.

    Returns:
    - User counts (total, active, by role)
    - Transaction totals (count, income, expenses, net balance)
    """
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()  # noqa: E712
    total_transactions = db.query(Transaction).count()

    income_total = (
        db.query(func.sum(Transaction.amount))
        .filter(Transaction.type == TransactionType.INCOME)
        .scalar()
        or 0.0
    )

    expense_total = (
        db.query(func.sum(Transaction.amount))
        .filter(Transaction.type == TransactionType.EXPENSE)
        .scalar()
        or 0.0
    )

    role_counts = (
        db.query(User.role, func.count(User.id))
        .group_by(User.role)
        .all()
    )

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "inactive": total_users - active_users,
            "by_role": {str(role.value): count for role, count in role_counts},
        },
        "transactions": {
            "total": total_transactions,
            "total_income": round(float(income_total), 2),
            "total_expenses": round(float(expense_total), 2),
            "net_balance": round(float(income_total) - float(expense_total), 2),
        },
    }
