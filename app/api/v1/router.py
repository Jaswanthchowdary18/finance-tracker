"""
Central API v1 router — assembles all endpoint groups.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, transactions, users, admin, export

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["Transactions"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(export.router, prefix="/export", tags=["Export"])