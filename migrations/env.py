from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.engine import engine_from_config

from backend.app.db.base import Base
from backend.app.db.session import database_url

import backend.app.models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Alembic이 SQLAlchemy 모델 구조를 확인할 때 사용한다.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """DB에 직접 연결하지 않고 SQL 스크립트 형태로 Migration을 실행한다."""

    url = database_url.render_as_string(hide_password=False)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """연결된 DB에서 Migration을 실행한다."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """PostgreSQL에 직접 연결하여 Migration을 실행한다."""

    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = database_url.render_as_string(
        hide_password=False
    )

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()