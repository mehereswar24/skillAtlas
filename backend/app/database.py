"""SQLAlchemy engine, session factory and declarative base.

SQLite is the default so the product runs with no infrastructure. The same
models work against Postgres by setting DATABASE_URL — avoid SQLite-only SQL.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

if settings.is_sqlite:
    connect_args: dict = {"check_same_thread": False}
    pool_kwargs: dict = {}
else:
    # Postgres, which in practice means a serverless function talking to a
    # managed database over the network. Three settings matter there and none
    # of them do locally:
    #
    # `pool_size`/`max_overflow` are small on purpose. Every warm instance
    # holds its own pool, so the connection count the database sees is
    # (instances x pool). Managed Postgres free tiers cap connections in the
    # low hundreds, and a pool sized for one big server exhausts that as soon
    # as the platform scales out. Point DATABASE_URL at the *pooled* endpoint
    # (PgBouncer, the `-pooler` host on Neon) and let it do the real pooling.
    #
    # `pool_recycle` is below the idle timeout managed providers use to reap
    # connections. Without it a warm-but-quiet instance keeps a handle the
    # server has already closed, and the next request fails once before
    # pre-ping opens a fresh one.
    #
    # `connect_timeout` stops a network problem from consuming the whole
    # function budget before the client sees anything.
    connect_args = {"connect_timeout": settings.db_connect_timeout_sec}
    pool_kwargs = {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_recycle": settings.db_pool_recycle_sec,
    }

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    # Verifies a pooled connection is alive before handing it over, at the cost
    # of one round trip. Load-bearing against a database that can close
    # connections underneath an idle instance.
    pool_pre_ping=True,
    future=True,
    **pool_kwargs,
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
