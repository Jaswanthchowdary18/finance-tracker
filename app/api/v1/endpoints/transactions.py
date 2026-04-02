"""
Transaction endpoints — CRUD + filtering + analytics.
Route order matters: /summary must be declared before /{transaction_id}
so FastAPI doesn't try to cast "summary" to an integer.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.transaction import TransactionType, Category
from app.models.user import User
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionOut,
    PaginatedTransactions,
    FinancialSummary,
)
from app.services.transaction_service import TransactionService
from app.utils.dependencies import get_current_user, require_analyst

router = APIRouter()


@router.post(
    "/",
    response_model=TransactionOut,
    status_code=201,
    summary="Create a transaction",
    responses={
        201: {"description": "Transaction created"},
        403: {"description": "Viewer role cannot create transactions"},
        422: {"description": "Validation error"},
    },
)
def create_transaction(
    data: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analyst),
):
    """
    Create a new income or expense record.

    **Requires**: Analyst or Admin role.
    """
    return TransactionService(db).create(data, current_user)


@router.get(
    "/",
    response_model=PaginatedTransactions,
    summary="List transactions with filters and pagination",
)
def list_transactions(
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page (max 100)"),
    type: Optional[TransactionType] = Query(None, description="Filter by `income` or `expense`"),
    category: Optional[Category] = Query(None, description="Filter by category"),
    start_date: Optional[date] = Query(None, description="Earliest date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Latest date (YYYY-MM-DD)"),
    min_amount: Optional[float] = Query(None, ge=0, description="Minimum transaction amount"),
    max_amount: Optional[float] = Query(None, ge=0, description="Maximum transaction amount"),
    search: Optional[str] = Query(None, min_length=1, max_length=100, description="Search in description"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve a paginated, filterable list of transactions.

    **Role behaviour:**
    - `viewer` / `analyst` — see only their own transactions
    - `admin` — sees all transactions across all users

    All filter parameters are optional and combinable.
    """
    return TransactionService(db).get_all(
        user=current_user,
        page=page,
        page_size=page_size,
        type_filter=type,
        category_filter=category,
        start_date=start_date,
        end_date=end_date,
        min_amount=min_amount,
        max_amount=max_amount,
        search=search,
    )


# ⚠️ /summary MUST be declared before /{transaction_id}
@router.get(
    "/summary",
    response_model=FinancialSummary,
    summary="Financial analytics summary",
)
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a comprehensive financial summary including:

    - **Totals**: income, expenses, current balance
    - **Category breakdown**: per-category totals with percentage share
    - **Monthly trends**: month-by-month income vs expense comparison
    - **Averages & extremes**: average and largest values per type
    - **Recent activity**: last 10 transactions

    **Available to all authenticated users.**
    Admins see system-wide data; others see only their own.
    """
    return TransactionService(db).get_summary(current_user)


@router.get(
    "/{transaction_id}",
    response_model=TransactionOut,
    summary="Get a single transaction by ID",
    responses={
        200: {"description": "Transaction found"},
        404: {"description": "Transaction not found"},
    },
)
def get_transaction(
    transaction_id: int = Path(..., ge=1, description="Transaction ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch a specific transaction by its ID."""
    return TransactionService(db).get_by_id(transaction_id, current_user)


@router.patch(
    "/{transaction_id}",
    response_model=TransactionOut,
    summary="Partially update a transaction",
    responses={
        200: {"description": "Transaction updated"},
        403: {"description": "Viewer role cannot update transactions"},
        404: {"description": "Transaction not found"},
        422: {"description": "Validation error or empty body"},
    },
)
def update_transaction(
    transaction_id: int = Path(..., ge=1, description="Transaction ID"),
    data: TransactionUpdate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_analyst),
):
    """
    Partially update a transaction. Only supply fields you want to change.
    Sending an empty body `{}` is rejected with a 422 error.

    **Requires**: Analyst or Admin role.
    """
    return TransactionService(db).update(transaction_id, data, current_user)


@router.delete(
    "/{transaction_id}",
    status_code=204,
    summary="Delete a transaction",
    responses={
        204: {"description": "Transaction deleted"},
        403: {"description": "Admin role required"},
        404: {"description": "Transaction not found"},
    },
)
def delete_transaction(
    transaction_id: int = Path(..., ge=1, description="Transaction ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Permanently delete a transaction record.

    **Requires**: Admin role.
    """
    TransactionService(db).delete(transaction_id, current_user)
