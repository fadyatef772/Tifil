"""SQLAlchemy engine and session factory.

The rest of the app depends only on `get_db` and `Base`, so moving from
SQLite to Postgres/Supabase is a one-line change in config — no call site
changes anywhere.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# check_same_thread is a SQLite-only flag; harmless to compute unconditionally.
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
