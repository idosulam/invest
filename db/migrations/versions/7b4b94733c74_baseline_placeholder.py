"""baseline placeholder — recreates lost migration history

The actual file that generated this revision was lost (created inside
a container without a persistent volume mount, before the mount was
added). The live database schema already reflects everything through
this revision, so this file is intentionally a no-op — it exists only
so Alembic's history has a node matching what's recorded in the
database's alembic_version table.

Revision ID: 7b4b94733c74
Revises: 
Create Date: recreated retroactively
"""
from alembic import op
import sqlalchemy as sa

revision = '7b4b94733c74'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass  # no-op — schema already matches this point


def downgrade() -> None:
    pass  # no-op
