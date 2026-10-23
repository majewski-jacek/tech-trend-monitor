from logging.config import fileConfig
import os
import sys

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Ensure app is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.models import Base

config = context.config

db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        from sqlalchemy import inspect
        inspector = inspect(connection)
        tables = inspector.get_table_names()
        has_articles = "articles" in tables
        has_alembic_ver = "alembic_version" in tables
        version_rows = []
        if has_alembic_ver:
            try:
                version_rows = connection.exec_driver_sql("SELECT version_num FROM alembic_version").fetchall()
            except Exception:
                version_rows = []

        # Self-heal unversioned or legacy database: if schema already exists but alembic_version is missing/empty
        if has_articles and (not has_alembic_ver or len(version_rows) == 0):
            from alembic.script import ScriptDirectory
            script = ScriptDirectory.from_config(config)
            head_rev = script.get_current_head()
            if not has_alembic_ver:
                connection.exec_driver_sql(
                    "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
                )
            connection.exec_driver_sql(
                f"INSERT INTO alembic_version (version_num) VALUES ('{head_rev}')"
            )
            connection.commit()

        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
