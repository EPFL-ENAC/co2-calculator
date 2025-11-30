import argparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

from app.core.config import get_settings


def parse_args():
    parser = argparse.ArgumentParser(description="Manage database (drop/create)")
    parser.add_argument("--action", choices=["drop", "create"], required=True)
    parser.add_argument("--db-name", type=str, default=None)
    return parser.parse_args()


settings = get_settings()
url_obj = make_url(settings.db_url)
default_db_name = url_obj.database


def get_default_db_url():
    url_obj = make_url(settings.db_url)
    if (
        url_obj.drivername == "postgresql"
        or url_obj.drivername == "postgres"
        or url_obj.drivername == "postgresql+psycopg"
    ) and not url_obj.drivername.endswith("+asyncpg"):
        # Add async driver + optional query params
        url_obj = url_obj.set(drivername="postgresql+psycopg")
    return str(url_obj).replace(url_obj.database, "postgres")


def drop_db(db_name):
    default_db_url = get_default_db_url()
    engine = create_engine(default_db_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
    engine.dispose()


def create_db(db_name):
    default_db_url = get_default_db_url()
    engine = create_engine(default_db_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {db_name}"))
    engine.dispose()


if __name__ == "__main__":
    args = parse_args()
    db_name = args.db_name or default_db_name
    if args.action == "drop":
        drop_db(db_name)
    elif args.action == "create":
        create_db(db_name)
