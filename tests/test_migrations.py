from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app import db


def test_migrations_build_the_same_schema_as_the_models(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")

    migrated = inspect(create_engine(url))
    columns = {c["name"] for c in migrated.get_columns("jobs")}
    assert columns == set(db.Base.metadata.tables["jobs"].columns.keys())

    command.downgrade(config, "base")
    assert "jobs" not in inspect(create_engine(url)).get_table_names()
