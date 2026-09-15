"""verify postgis extension is usable on the target database

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-28

Confirms the target database (Supabase, PostGIS enabled in the dashboard)
actually serves PostGIS functions. If this migration fails, the PostGIS
extension is not enabled — enable it under Supabase Database > Extensions.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # Real PostGIS function check (online mode only): ST_AsText(ST_Point(0,0))
    # must return 'POINT(0 0)'. Raises if the function is missing (extension
    # not enabled). In offline (--sql) mode there is no live connection, so
    # the statement is emitted but not executed.
    conn = op.get_bind()
    if conn is not None:
        result = conn.execute(sa.text("SELECT ST_AsText(ST_Point(0,0))")).scalar()
        assert result == "POINT(0 0)", f"PostGIS not functional on target DB: got {result!r}"


def downgrade() -> None:
    pass  # PostGIS stays enabled; nothing to roll back
