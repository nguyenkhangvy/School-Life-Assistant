from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import upgrade

from app import create_app
from app.extensions import db
from tests.helpers import make_config

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")


def test_migrations_build_exactly_the_tables_the_models_describe(tmp_path):
    # Fails when someone changes a model but forgets `flask db migrate`.
    app = create_app(make_config(SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'migrated.db'}"))

    with app.app_context():
        upgrade(directory=MIGRATIONS_DIR)
        with db.engine.connect() as connection:
            differences = compare_metadata(MigrationContext.configure(connection), db.metadata)
        db.engine.dispose()

    assert differences == []
