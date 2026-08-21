"""SQLAlchemy engine, session factory and declarative base.

SQLite is the default so the product runs with no infrastructure. The same
models work against Postgres by setting DATABASE_URL — avoid SQLite-only SQL.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)

if settings.is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _connection_record):
        """SQLite ignores foreign keys unless asked; WAL keeps reads concurrent.

        ``isolation_level = None`` turns off pysqlite's own transaction
        handling. Left on, the driver opens and commits transactions behind
        SQLAlchemy's back, which silently breaks SAVEPOINT: the test suite's
        rollback-per-test isolation released its savepoint outside any
        transaction and rows leaked between tests. SQLAlchemy's pysqlite
        dialect documents this exact workaround, with the explicit BEGIN below
        as its other half.
        """
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _sqlite_begin(conn):
        """Emit the BEGIN that pysqlite no longer emits for us."""
        conn.exec_driver_sql("BEGIN")


SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, future=True
)


class Base(DeclarativeBase):
    """Declarative base for every model in app.models."""


def get_db():
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
