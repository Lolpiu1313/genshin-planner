import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///genshin.db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


# SQLite ignores foreign keys unless enabled per connection
if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _enable_fks(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")


def get_session():
    with SessionLocal() as session:
        yield session
