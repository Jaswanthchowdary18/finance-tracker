"""
Export endpoints — download transactions as CSV or JSON.
Available to all authenticated users (scoped by role: admins get all, others get own).
"""

import csv
import io
import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.transaction import Transaction, TransactionType, Category
from app.models.user import User, UserRole
from app.utils.dependencies import get_current_user

router = APIRouter()


def _build_query(db: Session, user: User, start_date=None, end_date=None,
                 type_filter=None, category_filter=None):
    q = db.query(Transaction)
    if user.role != UserRole.ADMIN:
        q = q.filter(Transaction.user_id == user.id)
    if type_filter:
        q = q.filter(Transaction.type == type_filter)
    if category_filter:
        q = q.filter(Transaction.category == category_filter)
    if start_date:
        q = q.filter(Transaction.date >= start_date)
    if end_date:
        q = q.filter(Transaction.date <= end_date)
    return q.order_by(Transaction.date.desc(), Transaction.id.desc())


@router.get(
    "/csv",
    summary="Export transactions as CSV",
    responses={
        200: {
            "description": "CSV file download",
            "content": {"text/csv": {}},
        }
    },
)
def export_csv(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    type: Optional[TransactionType] = Query(None),
    category: Optional[Category] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download transactions as a CSV file.

    Applies the same role-based scoping as the transactions list endpoint.
    All filter parameters are optional.
    """
    transactions = _build_query(
        db, current_user, start_date, end_date, type, category
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "date", "type", "category", "amount", "description", "user_id", "created_at"])

    for tx in transactions:
        writer.writerow([
            tx.id,
            tx.date.isoformat(),
            tx.type.value,
            tx.category.value,
            str(tx.amount),
            tx.description or "",
            tx.user_id,
            tx.created_at.isoformat(),
        ])

    output.seek(0)
    filename = f"transactions_{date.today().isoformat()}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/json",
    summary="Export transactions as JSON",
    responses={
        200: {
            "description": "JSON file download",
            "content": {"application/json": {}},
        }
    },
)
def export_json(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    type: Optional[TransactionType] = Query(None),
    category: Optional[Category] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download transactions as a JSON file.

    Returns a structured JSON document with metadata and transaction array.
    """
    transactions = _build_query(
        db, current_user, start_date, end_date, type, category
    ).all()

    payload = {
        "exported_at": date.today().isoformat(),
        "exported_by": current_user.email,
        "filters": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "type": type.value if type else None,
            "category": category.value if category else None,
        },
        "total": len(transactions),
        "transactions": [
            {
                "id": tx.id,
                "date": tx.date.isoformat(),
                "type": tx.type.value,
                "category": tx.category.value,
                "amount": str(tx.amount),
                "description": tx.description,
                "user_id": tx.user_id,
                "created_at": tx.created_at.isoformat(),
            }
            for tx in transactions
        ],
    }

    content = json.dumps(payload, indent=2, ensure_ascii=False)
    filename = f"transactions_{date.today().isoformat()}.json"

    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
