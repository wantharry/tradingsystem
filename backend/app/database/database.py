"""
database.py — Database connection and session management.

WHY SQLITE:
  SQLite requires zero setup, stores everything in a single file, and is
  perfectly capable of handling years of daily OHLCV data for hundreds of
  symbols. You can switch to PostgreSQL simply by changing DATABASE_URL in .env.
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

# Ensure the data directory exists before creating the database file
os.makedirs("data", exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite with FastAPI
    echo=settings.DEBUG,
)

# Enable WAL mode for SQLite — allows concurrent reads while writing
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session and ensures it's closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Called once at startup."""
    from app.database import models  # noqa: F401 — import triggers model registration
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created/verified")
