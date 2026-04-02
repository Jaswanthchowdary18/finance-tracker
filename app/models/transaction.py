"""
Transaction model — the core financial record.
Stores income and expense entries with rich metadata.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Numeric, Date, DateTime,
    ForeignKey, Text, Enum as SAEnum, CheckConstraint,
)
from sqlalchemy.orm import relationship
import enum

from app.db.database import Base


class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class Category(str, enum.Enum):
    # Income categories
    SALARY = "salary"
    FREELANCE = "freelance"
    INVESTMENT = "investment"
    GIFT = "gift"
    OTHER_INCOME = "other_income"

    # Expense categories
    FOOD = "food"
    HOUSING = "housing"
    TRANSPORT = "transport"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    ENTERTAINMENT = "entertainment"
    SHOPPING = "shopping"
    UTILITIES = "utilities"
    TRAVEL = "travel"
    OTHER_EXPENSE = "other_expense"


class Transaction(Base):
    __tablename__ = "transactions"

    # Use Numeric for exact decimal money storage (avoid float rounding errors)
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transaction_amount_positive"),
    )

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Numeric(precision=15, scale=2), nullable=False)
    type = Column(SAEnum(TransactionType), nullable=False, index=True)
    category = Column(SAEnum(Category), nullable=False, index=True)
    description = Column(Text, nullable=True)
    date = Column(Date, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Foreign key linking to the owning user
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner = relationship("User", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction id={self.id} type={self.type} amount={self.amount}>"
