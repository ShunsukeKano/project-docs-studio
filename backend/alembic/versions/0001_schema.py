"""Create the Docs Studio schema from db-automation-apply/001_schema.sql.

Revision ID: 0001
Revises:
"""

from pathlib import Path

from alembic import op
from sqlalchemy.util import await_only

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "db-automation-apply" / "001_schema.sql"


def upgrade() -> None:
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    # The file holds many commands, including functions and triggers, so it cannot go through a
    # prepared statement. asyncpg's own execute() with no arguments uses the simple-query path.
    raw = op.get_bind().connection.driver_connection
    await_only(raw.execute(sql))


def downgrade() -> None:
    # Dropping the tables also drops their triggers and indexes; the functions are dropped last.
    op.execute("DROP TABLE IF EXISTS articles CASCADE")
    op.execute("DROP TABLE IF EXISTS article_versions CASCADE")
    op.execute("DROP FUNCTION IF EXISTS articles_guard()")
    op.execute("DROP FUNCTION IF EXISTS forbid_version_truncate()")
    op.execute("DROP FUNCTION IF EXISTS forbid_version_update()")
