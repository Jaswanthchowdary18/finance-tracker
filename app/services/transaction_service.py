"""
Transaction Service — all business logic for financial records and analytics.
Uses SQL-level aggregations for performance. This is the heart of the application.
"""

from datetime import date
from decimal import Decimal
from typing import Optional, List
from collections import defaultdict
from calendar import month_name as MONTH_NAMES

from sqlalchemy.orm import Session
from sqlalchemy import func, extract, case
from fastapi import HTTPException, status

from app.models.transaction import Transaction, TransactionType, Category
from app.models.user import User, UserRole
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    FinancialSummary,
    CategoryBreakdown,
    MonthlyTotal,
    PaginatedTransactions,
    TransactionOut,
)
from app.core.config import settings


class TransactionService:
    def __init__(self, db: Session):
        self.db = db

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _base_query(self, user: User):
        """
        Admins see all transactions; others only see their own.
        """
        q = self.db.query(Transaction)
        if user.role != UserRole.ADMIN:
            q = q.filter(Transaction.user_id == user.id)
        return q

    def _get_or_404(self, transaction_id: int, user: User) -> Transaction:
        tx = self._base_query(user).filter(Transaction.id == transaction_id).first()
        if not tx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction {transaction_id} not found.",
            )
        return tx

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create(self, data: TransactionCreate, user: User) -> Transaction:
        """Create a new transaction owned by the current user."""
        tx = Transaction(
            amount=data.amount,
            type=data.type,
            category=data.category,
            description=data.description,
            date=data.date,
            user_id=user.id,
        )
        self.db.add(tx)
        self.db.commit()
        self.db.refresh(tx)
        return tx

    def get_all(
        self,
        user: User,
        page: int = 1,
        page_size: int = 20,
        type_filter: Optional[TransactionType] = None,
        category_filter: Optional[Category] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        search: Optional[str] = None,
    ) -> PaginatedTransactions:
        """
        Retrieve transactions with optional filters and pagination.
        Viewers and analysts see only their own; admins see all.
        """
        # Clamp page size
        page_size = min(page_size, settings.MAX_PAGE_SIZE)
        page = max(page, 1)

        q = self._base_query(user)

        # Apply filters
        if type_filter:
            q = q.filter(Transaction.type == type_filter)
        if category_filter:
            q = q.filter(Transaction.category == category_filter)
        if start_date:
            q = q.filter(Transaction.date >= start_date)
        if end_date:
            q = q.filter(Transaction.date <= end_date)
        if min_amount is not None:
            q = q.filter(Transaction.amount >= Decimal(str(min_amount)))
        if max_amount is not None:
            q = q.filter(Transaction.amount <= Decimal(str(max_amount)))
        if search:
            q = q.filter(Transaction.description.ilike(f"%{search}%"))

        total = q.count()
        total_pages = max(1, -(-total // page_size))  # ceiling division

        items = (
            q.order_by(Transaction.date.desc(), Transaction.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return PaginatedTransactions(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=items,
        )

    def get_by_id(self, transaction_id: int, user: User) -> Transaction:
        return self._get_or_404(transaction_id, user)

    def update(self, transaction_id: int, data: TransactionUpdate, user: User) -> Transaction:
        """Update a transaction. Viewers cannot update."""
        if user.role == UserRole.VIEWER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Viewers cannot modify transactions.",
            )
        tx = self._get_or_404(transaction_id, user)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(tx, field, value)
        self.db.commit()
        self.db.refresh(tx)
        return tx

    def delete(self, transaction_id: int, user: User) -> None:
        """Delete a transaction. Only admins can delete."""
        if user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can delete transactions.",
            )
        tx = self._get_or_404(transaction_id, user)
        self.db.delete(tx)
        self.db.commit()

    # ── Analytics (SQL-level aggregations — no Python loops over all rows) ──

    def get_summary(self, user: User) -> FinancialSummary:
        """
        Generate a comprehensive financial summary using SQL aggregations.
        Includes:
        - Totals and balance
        - Category breakdown with percentages
        - Monthly income vs expense trends
        - Recent activity
        """
        base_q = self._base_query(user)

        # ── Totals via SQL ────────────────────────────────────────────────
        agg = (
            base_q.with_entities(
                func.count(Transaction.id).label("total_count"),
                func.coalesce(
                    func.sum(
                        case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)
                    ), 0
                ).label("total_income"),
                func.coalesce(
                    func.sum(
                        case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)
                    ), 0
                ).label("total_expenses"),
                func.count(
                    case((Transaction.type == TransactionType.INCOME, Transaction.id))
                ).label("income_count"),
                func.count(
                    case((Transaction.type == TransactionType.EXPENSE, Transaction.id))
                ).label("expense_count"),
                func.coalesce(
                    func.avg(
                        case((Transaction.type == TransactionType.INCOME, Transaction.amount))
                    ), 0
                ).label("avg_income"),
                func.coalesce(
                    func.avg(
                        case((Transaction.type == TransactionType.EXPENSE, Transaction.amount))
                    ), 0
                ).label("avg_expense"),
                func.coalesce(
                    func.max(
                        case((Transaction.type == TransactionType.INCOME, Transaction.amount))
                    ), 0
                ).label("max_income"),
                func.coalesce(
                    func.max(
                        case((Transaction.type == TransactionType.EXPENSE, Transaction.amount))
                    ), 0
                ).label("max_expense"),
            )
            .one()
        )

        total_income = round(float(agg.total_income), 2)
        total_expenses = round(float(agg.total_expenses), 2)
        current_balance = round(total_income - total_expenses, 2)

        # ── Category breakdown via SQL ────────────────────────────────────
        cat_rows = (
            base_q.with_entities(
                Transaction.category.label("category"),
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("count"),
            )
            .group_by(Transaction.category)
            .order_by(func.sum(Transaction.amount).desc())
            .all()
        )

        grand_total = total_income + total_expenses
        category_breakdown = [
            CategoryBreakdown(
                category=row.category.value,
                total=round(float(row.total), 2),
                count=row.count,
                percentage=round((float(row.total) / grand_total * 100), 2) if grand_total else 0.0,
            )
            for row in cat_rows
        ]

        # ── Monthly totals via SQL ────────────────────────────────────────
        month_rows = (
            base_q.with_entities(
                extract("year", Transaction.date).label("year"),
                extract("month", Transaction.date).label("month"),
                func.coalesce(
                    func.sum(
                        case((Transaction.type == TransactionType.INCOME, Transaction.amount), else_=0)
                    ), 0
                ).label("income"),
                func.coalesce(
                    func.sum(
                        case((Transaction.type == TransactionType.EXPENSE, Transaction.amount), else_=0)
                    ), 0
                ).label("expenses"),
            )
            .group_by(
                extract("year", Transaction.date),
                extract("month", Transaction.date),
            )
            .order_by(
                extract("year", Transaction.date),
                extract("month", Transaction.date),
            )
            .all()
        )

        monthly_totals = [
            MonthlyTotal(
                year=int(row.year),
                month=int(row.month),
                month_name=MONTH_NAMES[int(row.month)],
                income=round(float(row.income), 2),
                expenses=round(float(row.expenses), 2),
                net=round(float(row.income) - float(row.expenses), 2),
            )
            for row in month_rows
        ]

        # ── Recent 10 transactions ────────────────────────────────────────
        recent = (
            base_q
            .order_by(Transaction.date.desc(), Transaction.id.desc())
            .limit(10)
            .all()
        )

        return FinancialSummary(
            total_income=total_income,
            total_expenses=total_expenses,
            current_balance=current_balance,
            transaction_count=agg.total_count,
            income_count=agg.income_count,
            expense_count=agg.expense_count,
            average_income=round(float(agg.avg_income), 2),
            average_expense=round(float(agg.avg_expense), 2),
            largest_income=round(float(agg.max_income), 2),
            largest_expense=round(float(agg.max_expense), 2),
            category_breakdown=category_breakdown,
            monthly_totals=monthly_totals,
            recent_transactions=recent,
        )
