"""SQLite setup and one transaction per API request."""

from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    if not url.startswith("sqlite:///"):
        raise ValueError("This assignment supports SQLite database URLs only.")
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 10})

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        # Explicit BEGIN below avoids sqlite3's legacy implicit transaction behavior.
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")

    return engine


def get_db(request: Request) -> Generator[Session]:
    with Session(request.app.state.engine, expire_on_commit=False) as session:
        # Acquire the write lock BEFORE reading members/balances. Concurrent writes
        # cannot both validate against the same outstanding debt and over-settle it.
        writing = request.method in {"POST", "PUT", "PATCH", "DELETE"}
        session.execute(text("BEGIN IMMEDIATE" if writing else "BEGIN"))
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
