"""create the initial application schema

Revision ID: 0826560045b9
Revises:
Create Date: 2026-08-21 15:40:04.845202
"""
from alembic import op
import sqlalchemy as sa


revision = "0826560045b9"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gym_owner",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=15), nullable=False),
        sa.Column("join_date", sa.Date(), nullable=True),
        sa.Column("payment_due_date", sa.Date(), nullable=True),
        sa.Column("owner_plan", sa.String(length=50), nullable=True),
        sa.Column("member_limit_warning_plan", sa.String(length=50), nullable=True),
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_member_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inactive_member_removal_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("send_reminder", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "membership_plan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=30), nullable=False),
        sa.Column("duration_months", sa.Integer(), nullable=False),
        sa.Column("fee", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.ForeignKeyConstraint(["owner_id"], ["gym_owner.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name", name="uq_owner_plan_name"),
    )
    op.create_table(
        "owner_payment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("subscription_start_date", sa.Date(), nullable=True),
        sa.Column("plan_name", sa.String(length=50), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["gym_owner.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "edit_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("actor_name", sa.String(length=100), nullable=True),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("context_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["gym_owner.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["gym_owner.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "member",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("address", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=15), nullable=False),
        sa.Column("join_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("membership_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("send_membership_reminder", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("current_plan_id", sa.Integer(), nullable=True),
        sa.Column("membership_start", sa.Date(), nullable=True),
        sa.Column("membership_expiry", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["current_plan_id"], ["membership_plan.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["gym_owner.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name", name="uq_owner_member_name"),
    )
    op.create_table(
        "membership",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=True),
        sa.Column("plan_name", sa.String(length=50), nullable=False),
        sa.Column("duration_months", sa.Integer(), nullable=False),
        sa.Column("fee", sa.Integer(), nullable=False),
        sa.Column("amount_paid", sa.Integer(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], ["member.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["membership_plan.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "attendance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("check_in", sa.DateTime(), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], ["member.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id", "attendance_date", name="uq_member_attendance"),
    )
    op.create_table(
        "automatic_message",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("phone", sa.String(length=15), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )

    op.create_index("ix_owner_payment_owner_id", "owner_payment", ["owner_id"])
    op.create_index("ix_owner_payment_owner_date", "owner_payment", ["owner_id", "payment_date"])
    op.create_index("ix_edit_history_owner_id", "edit_history", ["owner_id"])
    op.create_index("ix_edit_history_entity_type", "edit_history", ["entity_type"])
    op.create_index("ix_edit_history_entity_id", "edit_history", ["entity_id"])
    op.create_index("ix_edit_history_context_id", "edit_history", ["context_id"])
    op.create_index("ix_edit_history_created_at", "edit_history", ["created_at"])
    op.create_index("ix_member_owner_id", "member", ["owner_id"])
    op.create_index("ix_member_owner_expiry", "member", ["owner_id", "membership_expiry"])
    op.create_index("ix_member_owner_join_date", "member", ["owner_id", "join_date"])
    op.create_index("ix_membership_member_id", "membership", ["member_id"])
    op.create_index("ix_membership_member_payment_date", "membership", ["member_id", "payment_date"])
    op.create_index("ix_membership_payment_date", "membership", ["payment_date"])
    op.create_index("ix_attendance_member_id", "attendance", ["member_id"])
    op.create_index("ix_attendance_member_date", "attendance", ["member_id", "attendance_date"])
    op.create_index("ix_attendance_date_member", "attendance", ["attendance_date", "member_id"])
    op.create_index("ix_automatic_message_dedupe_key", "automatic_message", ["dedupe_key"])
    op.create_index("ix_automatic_message_created_at", "automatic_message", ["created_at"])
    op.create_index("ix_automatic_message_sent_at", "automatic_message", ["sent_at"])


def downgrade():
    op.drop_table("automatic_message")
    op.drop_table("attendance")
    op.drop_table("membership")
    op.drop_table("member")
    op.drop_table("edit_history")
    op.drop_table("owner_payment")
    op.drop_table("membership_plan")
    op.drop_table("gym_owner")
