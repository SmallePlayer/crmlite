"""initial

Revision ID: abe8f8dc9e3a
Revises: 
Create Date: 2026-06-25 08:36:38.488067

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'abe8f8dc9e3a'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
