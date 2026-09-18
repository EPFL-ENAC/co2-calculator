import argparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

from app.core.config import get_settings

LOCAL_HOSTS = frozenset({None, "", "localhost", "127.0.0.1", "::1", "db"})


def parse_args():
    parser = argparse.ArgumentParser(description="Manage database (drop/create)")
    parser.add_argument("--action", choices=["drop", "create"], required=True)
    parser.add_argument("--db-name", type=str, default=None)
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="act on a database host that is not local (dev/stage/prod DBaaS)",
    )
    return parser.parse_args()


def refuse_remote_host(db_url: str, allow_remote: bool) -> None:
    """Refuse to drop or create on a shared server unless asked in so many words.

    Deliberately independent of *which* settings source produced ``db_url``
    (.env vs. env var vs. default) — see app/core/config.py's Settings.
    model_config comment. Whichever one wins, prod is how it was dropped on
    2026-09-08: a resolved URL nobody double-checked was local.
    """
    host = make_url(db_url).host
    if host in LOCAL_HOSTS or allow_remote:
        return
    raise SystemExit(
        f"refusing: DB_URL points at {host!r}, not a local host. "
        "Check backend/.env; pass --allow-remote if you really mean it."
    )


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
    port = url_obj.port
    url_obj = url_obj.set(database="postgres", port=port)
    if url_obj.drivername in [
        "postgresql",
        "postgres",
        "postgresql+psycopg",
    ] and not url_obj.drivername.endswith("+asyncpg"):
        url_obj = url_obj.set(drivername="postgresql+psycopg")
    return url_obj


def drop_db(db_name):
    # This now returns a URL Object with the correct password and user 'postgres'
    default_db_url = get_default_db_url()
    print(f"Dropping database using URL: {default_db_url}")
    print(f"Dropping database: {db_name}")

    # create_engine accepts the URL object directly
    engine = create_engine(default_db_url, isolation_level="AUTOCOMMIT")

    with engine.connect() as conn:
        # Terminate existing connections
        # conn.execute(
        #     text(
        #         """
        #         SELECT pg_terminate_backend(pid)
        #         FROM pg_stat_activity
        #         WHERE datname = :db_name AND pid <> pg_backend_pid();
        #         """
        #     ),
        #     {"db_name": db_name},
        # )
        conn.execute(text(f"DROP DATABASE IF EXISTS {db_name} with (force);"))
    engine.dispose()


def create_db(db_name):
    default_db_url = get_default_db_url()
    print(f"Creating database using URL: {default_db_url}")
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
    refuse_remote_host(settings.DB_URL, args.allow_remote)
    db_name = args.db_name or default_db_name
    if args.action == "drop":
        drop_db(db_name)
    elif args.action == "create":
        create_db(db_name)
