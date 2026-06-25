"""add_missing_columns

Revision ID: 16c295deb0d2
Revises: abe8f8dc9e3a
Create Date: 2026-06-25 08:43:47.809171

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '16c295deb0d2'
down_revision: Union[str, Sequence[str], None] = 'abe8f8dc9e3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "sqlite":
        existing_cols = {
            row[1] for row in conn.execute(
                sa.text("PRAGMA table_info(roles)")
            ).fetchall()
        }
    else:
        existing_cols = set()

    def add_col(table, column):
        if column.name not in existing_cols or dialect != "sqlite":
            try:
                op.add_column(table, column)
            except Exception:
                pass

    add_col("roles", sa.Column("can_view_reports", sa.Boolean(), server_default=sa.text("0")))
    add_col("roles", sa.Column("can_edit_reports", sa.Boolean(), server_default=sa.text("0")))
    add_col("roles", sa.Column("can_view_warehouse", sa.Boolean(), server_default=sa.text("0")))
    add_col("roles", sa.Column("can_edit_warehouse", sa.Boolean(), server_default=sa.text("0")))
    add_col("roles", sa.Column("can_assign_tasks", sa.Boolean(), server_default=sa.text("0")))

    # Добавляем колонку admin_controlled в tasks
    if dialect == "sqlite":
        existing_task_cols = {
            row[1] for row in conn.execute(
                sa.text("PRAGMA table_info(tasks)")
            ).fetchall()
        }
    else:
        existing_task_cols = set()

    if "admin_controlled" not in existing_task_cols or dialect != "sqlite":
        try:
            op.add_column("tasks", sa.Column("admin_controlled", sa.Boolean(), server_default=sa.text("0")))
        except Exception:
            pass

    # Добавляем колонку custom_name в order_items
    if dialect == "sqlite":
        existing_oi_cols = {
            row[1] for row in conn.execute(
                sa.text("PRAGMA table_info(order_items)")
            ).fetchall()
        }
    else:
        existing_oi_cols = set()

    if "custom_name" not in existing_oi_cols or dialect != "sqlite":
        try:
            op.add_column("order_items", sa.Column("custom_name", sa.String(255), nullable=True))
        except Exception:
            pass


def downgrade() -> None:
    pass
