"""
Database engine and session factory.
Uses SQLAlchemy with SQLite by default.
Swap DATABASE_URL in .env for PostgreSQL or MySQL.
"""

from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

from app.core.config import settings

# SQLite needs check_same_thread=False for multi-threaded use
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,  # Set True to see raw SQL queries in logs
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def get_db():
    """
    FastAPI dependency that provides a database session per request.
    Automatically closes the session after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Auto-update `updated_at` on every flush ──────────────────────────────────
@event.listens_for(Session, "before_flush")
def _set_updated_at(session: Session, flush_context, instances):
    """
    Automatically set `updated_at` to now() whenever a mapped object
    is dirty (i.e. has pending changes). This is more reliable than
    SQLAlchemy's `onupdate=` keyword for in-process mutations.
    """
    now = datetime.now(timezone.utc)
    for obj in session.dirty:
        if hasattr(obj, "updated_at"):
            obj.updated_at = now
