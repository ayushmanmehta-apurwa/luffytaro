"""Database engine and session helpers. SQLite for local use, PostgreSQL via DATABASE_URL in production."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from . import config
from .models import Base

_is_sqlite = config.DATABASE_URL.startswith('sqlite')
engine = create_engine(
    config.DATABASE_URL,
    connect_args={'check_same_thread': False} if _is_sqlite else {},
    pool_pre_ping=not _is_sqlite,
)
if _is_sqlite:
    @event.listens_for(engine, 'connect')
    def _sqlite_pragmas(dbapi_connection, _record):
        cur = dbapi_connection.cursor()
        cur.execute('PRAGMA journal_mode=WAL')
        cur.execute('PRAGMA busy_timeout=30000')
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=True, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
