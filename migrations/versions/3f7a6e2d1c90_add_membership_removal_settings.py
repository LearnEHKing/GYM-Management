"""add membership removal settings

Revision ID: 3f7a6e2d1c90
Revises: 0826560045b9
"""
from alembic import op
import sqlalchemy as sa


revision = "3f7a6e2d1c90"
down_revision = "0826560045b9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("gym_owner", sa.Column("membership_removal_policy", sa.String(length=20), nullable=False, server_default="expire"))
    op.add_column("member", sa.Column("reserved_membership_days", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("gym_owner", "membership_removal_policy", server_default=None)
    op.alter_column("member", "reserved_membership_days", server_default=None)


def downgrade():
    op.drop_column("member", "reserved_membership_days")
    op.drop_column("gym_owner", "membership_removal_policy")