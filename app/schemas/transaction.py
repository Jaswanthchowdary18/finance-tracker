"""
Transaction schemas — Pydantic models for request/response handling.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator, model_validator

from app.models.transaction import TransactionType, Category


# ── Request Schemas ──────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    """Schema for creating a new transaction."""
    amount: Decimal
    type: TransactionType
    category: Category
    description: Optional[str] = None
    date: date

    @field_validator("amount", mode="before")
    @classmethod
    def amount_must_be_positive(cls, v) -> Decimal:
        v = Decimal(str(v))
        if v <= 0:
            raise ValueError("Amount must be greater than zero.")
        if v > Decimal("10000000"):
            raise ValueError("Amount exceeds maximum allowed value of 10,000,000.")
        return v.quantize(Decimal("0.01"))

    @field_validator("description")
    @classmethod
    def description_max_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 500:
                raise ValueError("Description cannot exceed 500 characters.")
            return v or None
        return v

    @field_validator("date")
    @classmethod
    def date_not_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Transaction date cannot be in the future.")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "amount": 5000.00,
                "type": "income",
                "category": "salary",
                "description": "Monthly salary",
                "date": "2024-01-15",
            }
        }
    }


class TransactionUpdate(BaseModel):
    """Schema for partially updating a transaction — all fields optional."""
    amount: Optional[Decimal] = None
    type: Optional[TransactionType] = None
    category: Optional[Category] = None
    description: Optional[str] = None
    date: Optional[date] = None

    @field_validator("amount", mode="before")
    @classmethod
    def amount_must_be_positive(cls, v) -> Optional[Decimal]:
        if v is None:
            return v
        v = Decimal(str(v))
        if v <= 0:
            raise ValueError("Amount must be greater than zero.")
        if v > Decimal("10000000"):
            raise ValueError("Amount exceeds maximum allowed value.")
        return v.quantize(Decimal("0.01"))

    @field_validator("date")
    @classmethod
    def date_not_in_future(cls, v: Optional[date]) -> Optional[date]:
        if v and v > date.today():
            raise ValueError("Transaction date cannot be in the future.")
        return v

    @model_validator(mode="after")
    def at_least_one_field(self) -> "TransactionUpdate":
        fields = {
            k: v for k, v in self.model_dump().items() if v is not None
        }
        if not fields:
            raise ValueError("At least one field must be provided for update.")
        return self


# ── Response Schemas ─────────────────────────────────────────────────────────

class TransactionOut(BaseModel):
    """Full transaction representation returned in API responses."""
    id: int
    amount: Decimal
    type: TransactionType
    category: Category
    description: Optional[str]
    date: date
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedTransactions(BaseModel):
    """Paginated list of transactions."""
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[TransactionOut]


# ── Analytics Schemas ────────────────────────────────────────────────────────

class CategoryBreakdown(BaseModel):
    category: str
    total: float
    count: int
    percentage: float


class MonthlyTotal(BaseModel):
    year: int
    month: int
    month_name: str
    income: float
    expenses: float
    net: float


class FinancialSummary(BaseModel):
    """Top-level financial summary returned by the analytics endpoint."""
    total_income: float
    total_expenses: float
    current_balance: float
    transaction_count: int
    income_count: int
    expense_count: int
    average_income: float
    average_expense: float
    largest_income: float
    largest_expense: float
    category_breakdown: List[CategoryBreakdown]
    monthly_totals: List[MonthlyTotal]
    recent_transactions: List[TransactionOut]
