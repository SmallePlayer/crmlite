from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, DeclarativeBase

from config import DB_URL

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _set_wal(dbapi_connection, _connection_record):
    dbapi_connection.execute("PRAGMA journal_mode=WAL")
    dbapi_connection.execute("PRAGMA synchronous=NORMAL")
    dbapi_connection.execute("PRAGMA cache_size=-8000")
    dbapi_connection.execute("PRAGMA temp_store=MEMORY")


def get_db():
    with Session(engine) as s:
        yield s


class Base(DeclarativeBase):
    pass
