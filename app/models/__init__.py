"""
Import all models here so SQLAlchemy's metadata is fully populated
before `Base.metadata.create_all()` is called.
Re-export Base so main.py can import it from one place.
"""
from app.db.database import Base                                           # noqa: F401
from app.models.user import User, UserRole                                 # noqa: F401
from app.models.transaction import Transaction, TransactionType, Category  # noqa: F401