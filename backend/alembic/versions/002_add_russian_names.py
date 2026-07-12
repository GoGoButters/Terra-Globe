"""Add Russian names for countries and capitals

Revision ID: 002_add_russian_names
Revises: 001_initial_schema
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa

revision = "002_add_russian_names"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("countries", sa.Column("name_ru", sa.String(200), nullable=True))
    op.add_column("countries", sa.Column("capital_name_ru", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("countries", "capital_name_ru")
    op.drop_column("countries", "name_ru")
