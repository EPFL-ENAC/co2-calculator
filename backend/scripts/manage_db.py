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
url_obj = make_url(settings.DB_URL)
default_db_name = url_obj.database


def get_default_db_url():
    url_obj = make_url(settings.DB_URL)

    # 1. Force the use of the 'postgres' superuser
    # 2. Force the connection to the 'postgres' maintenance database
    # Note: This assumes the password for 'postgres' is the same as in DB_URL.
    # Based on your Helm chart (adminPasswordKey matching userPasswordKey)
    #  this is correct.
    url_obj = url_obj.set(username="postgres", database="postgres")

    # Handle Async/Sync driver adjustment if needed (from your original logic)
    if url_obj.drivername in [
        "postgresql",
        "postgres",
        "postgresql+psycopg",
    ] and not url_obj.drivername.endswith("+asyncpg"):
        url_obj = url_obj.set(drivername="postgresql+psycopg")

    # Return the OBJECT, not a string. create_engine handles URL objects correctly.
    return url_obj


def drop_db(db_name):
    # This now returns a URL Object with the correct password and user 'postgres'
    default_db_url = get_default_db_url()

    # create_engine accepts the URL object directly
    engine = create_engine(default_db_url, isolation_level="AUTOCOMMIT")

    with engine.connect() as conn:
        # Terminate existing connections
        conn.execute(
            text(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = :db_name AND pid <> pg_backend_pid();
                """
            ),
            {"db_name": db_name},
        )
        conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
    engine.dispose()


def create_db(db_name):
    default_db_url = get_default_db_url()

    # Get the app user (co2_user) from your config
    # We assume the username in settings.DB_URL is 'co2_user'
    app_user = make_url(settings.DB_URL).username

    engine = create_engine(default_db_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        # quoted_name ensures special characters don't break the SQL
        # We explicitly set OWNER to co2_user
        conn.execute(text(f'CREATE DATABASE "{db_name}" OWNER "{app_user}"'))

    engine.dispose()


if __name__ == "__main__":
    args = parse_args()
    db_name = args.db_name or default_db_name
    if args.action == "drop":
        drop_db(db_name)
    elif args.action == "create":
        create_db(db_name)
