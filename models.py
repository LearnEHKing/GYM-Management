from datetime import date, datetime
from zoneinfo import ZoneInfo
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

import config

db = SQLAlchemy()
INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")


def local_now():
    """Return the current Asia/Kolkata time as a naive database datetime."""
    return datetime.now(INDIA_TIMEZONE).replace(tzinfo=None)


def local_today():
    return local_now().date()


class GymOwner(UserMixin, db.Model):
    __tablename__ = "gym_owner"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)

    join_date = db.Column(db.Date, default=local_today)
    payment_due_date = db.Column(db.Date)
    # Key of the platform subscription in config.plan.
    owner_plan = db.Column(db.String(50))
    # Plan for which the capacity warning has already been sent.
    member_limit_warning_plan = db.Column(db.String(50))

    # Number of free trial days for new members
    trial_days = db.Column(db.Integer, nullable=False, default=0)

    active_member_count = db.Column(db.Integer, nullable=False, default=0)

    # Remove active members after this many consecutive days without a visit.
    inactive_member_removal_days = db.Column(db.Integer, nullable=False, default=30)
    # Whether removal expires a current membership or pauses its remaining days.
    membership_removal_policy = db.Column(db.String(20), nullable=False, default="expire")

    #If gym owner wants to send automatic whatsapp payment reminder.
    send_reminder = db.Column(db.Boolean, nullable=False, default=False)
  
    owner_payments = db.relationship(
        "OwnerPayment",
        backref="owner",
        lazy=True,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    members = db.relationship(
        "Member",
        backref="owner",
        lazy=True,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    plans = db.relationship(
        "MembershipPlan",
        backref="owner",
        lazy=True,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def whatsapp_enabled(self):
        return bool(self.owner_plan and config.plan.get(self.owner_plan, {}).get("whatsapp_enabled"))


class OwnerPayment(db.Model):
    __tablename__ = "owner_payment"

    id = db.Column(db.Integer, primary_key=True)

    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("gym_owner.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    amount = db.Column(db.Integer, nullable=False)
    payment_date = db.Column(db.Date, default=local_today, nullable=False)
    subscription_start_date = db.Column(db.Date)
    # Snapshot of the selected platform subscription at payment time.
    plan_name = db.Column(db.String(50))
    remarks = db.Column(db.Text)

    __table_args__ = (
        db.Index("ix_owner_payment_owner_date", "owner_id", "payment_date"),
    )


class EditHistory(db.Model):
    __tablename__ = "edit_history"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("gym_owner.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("gym_owner.id", ondelete="CASCADE"), nullable=False)
    actor_name = db.Column(db.String(100))
    entity_type = db.Column(db.String(30), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    context_id = db.Column(db.Integer, index=True)
    action = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    before_data = db.Column(db.JSON)
    after_data = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=local_now, nullable=False, index=True)


class MembershipPlan(db.Model):
    __tablename__ = "membership_plan"

    id = db.Column(db.Integer, primary_key=True)

    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("gym_owner.id", ondelete="CASCADE"),
        nullable=False
    )

    name = db.Column(db.String(30), nullable=False)
    duration_months = db.Column(db.Integer, nullable=False)
    fee = db.Column(db.Integer, nullable=False)

    active = db.Column(db.Boolean, default=True)

    __table_args__ = (
        db.UniqueConstraint(
            "owner_id",
            "name",
            name="uq_owner_plan_name"
        ),
    )


class Member(db.Model):
    __tablename__ = "member"

    id = db.Column(db.Integer, primary_key=True)

    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("gym_owner.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(15), nullable=False)

    join_date = db.Column(db.Date, nullable=False)

    notes = db.Column(db.Text)
    membership_active = db.Column(db.Boolean, default=True, nullable=False)
    reserved_membership_days = db.Column(db.Integer, nullable=False, default=0)
    send_membership_reminder = db.Column(db.Boolean, default=True)
    current_plan_id = db.Column(
        db.Integer,
        db.ForeignKey("membership_plan.id", ondelete="SET NULL")
    )

    current_plan = db.relationship("MembershipPlan", foreign_keys=[current_plan_id])

    @property
    def is_trial(self):
        return self.current_plan_id is None and self.membership_expiry is not None

    membership_start = db.Column(db.Date)
    membership_expiry = db.Column(db.Date)
    memberships = db.relationship(
        "Membership",
        backref="member",
        lazy=True,
        cascade="all, delete-orphan"
    )

    attendance = db.relationship(
        "Attendance",
        backref="member",
        lazy=True,
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "owner_id",
            "name",
            name="uq_owner_member_name"
        ),
        db.Index("ix_member_owner_expiry", "owner_id", "membership_expiry"),
        db.Index("ix_member_owner_join_date", "owner_id", "join_date"),
    )

    @property
    def current_membership(self):
        return (
            Membership.query
            .filter_by(member_id=self.id)
            .order_by(
                Membership.expiry_date.desc(),
                Membership.id.desc()
            )
            .first()
        )

    @property
    def whatsapp_enabled(self):
        return bool(self.owner and self.owner.owner_plan and config.plan.get(self.owner.owner_plan, {}).get("whatsapp_enabled"))

    @property
    def latest_membership(self):
        return self.current_membership


class Membership(db.Model):
    __tablename__ = "membership"

    id = db.Column(db.Integer, primary_key=True)

    member_id = db.Column(
        db.Integer,
        db.ForeignKey("member.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    plan_id = db.Column(
        db.Integer,
        db.ForeignKey("membership_plan.id", ondelete="SET NULL")
    )

    plan = db.relationship("MembershipPlan")

    # Snapshot of plan at purchase time
    plan_name = db.Column(db.String(50), nullable=False)
    duration_months = db.Column(db.Integer, nullable=False)

    fee = db.Column(db.Integer, nullable=False)
    amount_paid = db.Column(db.Integer, nullable=False)

    payment_date = db.Column(
        db.Date,
        nullable=False,
        default=local_today
    )

    start_date = db.Column(db.Date, nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)

    remarks = db.Column(db.Text, default="")

    __table_args__ = (
        db.Index("ix_membership_member_payment_date", "member_id", "payment_date"),
        db.Index("ix_membership_payment_date", "payment_date"),
    )


class Attendance(db.Model):
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)

    member_id = db.Column(
        db.Integer,
        db.ForeignKey("member.id", ondelete="CASCADE"),
        nullable=False
    )

    check_in = db.Column(
        db.DateTime,
        nullable=False,
        default=local_now
    )

    attendance_date = db.Column(
        db.Date,
        nullable=False,
        default=local_today
    )

    notes = db.Column(db.String(100))

    __table_args__ = (
        db.UniqueConstraint(
            "member_id",
            "attendance_date",
            name="uq_member_attendance"
        ),
        db.Index("ix_attendance_member_date", "member_id", "attendance_date"),
        db.Index("ix_attendance_date_member", "attendance_date", "member_id"),
    )


class AutomaticMessage(db.Model):
    """A durable outbox for automatic WhatsApp messages.

    Keeping the message body in the database means a reminder deferred by the
    daily quota survives application restarts and can be delivered later.
    """

    __tablename__ = "automatic_message"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    message = db.Column(db.Text, nullable=False)
    # Identifies the event that produced this message and prevents duplicate
    # reminders when a scheduled job is run more than once.
    dedupe_key = db.Column(db.String(200), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=local_now, index=True)
    sent_at = db.Column(db.DateTime, index=True)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    last_error = db.Column(db.Text)
