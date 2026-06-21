from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().sqlalchemy_database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_schema_updates()


def ensure_schema_updates() -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "users" in table_names:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "currency_code" not in user_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE users ADD COLUMN currency_code VARCHAR(3) NOT NULL DEFAULT 'USD'"))

    if "categories" not in table_names:
        return

    category_columns = {column["name"] for column in inspector.get_columns("categories")}
    if "include_in_totals" not in category_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE categories ADD COLUMN include_in_totals BOOLEAN NOT NULL DEFAULT TRUE"))
        category_columns.add("include_in_totals")

    if "family_id" not in category_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE categories ADD COLUMN family_id INTEGER REFERENCES families(id)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_categories_family_id ON categories (family_id)"))
