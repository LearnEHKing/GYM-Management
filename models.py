from datetime import date, datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class GymOwner(UserMixin, db.Model):
    __tablename__ = "gym_owner"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)

    join_date = db.Column(db.Date, default=date.today)
    payment_due_date = db.Column(db.Date)

    # Number of free trial days for new members
    trial_days = db.Column(db.Integer, nullable=False, default=0)

    owner_payments = db.relationship(
        "OwnerPayment",
        backref="owner",
        lazy=True,
        cascade="all, delete-orphan"
    )

    members = db.relationship(
        "Member",
        backref="owner",
        lazy=True,
        cascade="all, delete-orphan"
    )

    plans = db.relationship(
        "MembershipPlan",
        backref="owner",
        lazy=True,
        cascade="all, delete-orphan"
    )


class OwnerPayment(db.Model):
    __tablename__ = "owner_payment"

    id = db.Column(db.Integer, primary_key=True)

    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("gym_owner.id"),
        nullable=False,
        index=True
    )

    amount = db.Column(db.Integer, nullable=False)
    payment_date = db.Column(db.Date, default=date.today, nullable=False)
    remarks = db.Column(db.Text)


class MembershipPlan(db.Model):
    __tablename__ = "membership_plan"

    id = db.Column(db.Integer, primary_key=True)

    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("gym_owner.id"),
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
        db.ForeignKey("gym_owner.id"),
        nullable=False,
        index=True
    )

    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(15), nullable=False)

    join_date = db.Column(db.Date, nullable=False)

    notes = db.Column(db.Text)

    active = db.Column(db.Boolean, default=True)

    current_plan_id = db.Column(
        db.Integer,
        db.ForeignKey("membership_plan.id")
    )

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
    )

    @property
    def latest_membership(self):
        return (
            Membership.query
            .filter_by(member_id=self.id)
            .order_by(
                Membership.payment_date.desc(),
                Membership.id.desc()
            )
            .first()
        )


class Membership(db.Model):
    __tablename__ = "membership"

    id = db.Column(db.Integer, primary_key=True)

    member_id = db.Column(
        db.Integer,
        db.ForeignKey("member.id"),
        nullable=False,
        index=True
    )

    plan_id = db.Column(
        db.Integer,
        db.ForeignKey("membership_plan.id")
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
        default=date.today
    )

    start_date = db.Column(db.Date, nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)

    remarks = db.Column(db.Text, default="")


class Attendance(db.Model):
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)

    member_id = db.Column(
        db.Integer,
        db.ForeignKey("member.id"),
        nullable=False
    )

    check_in = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    attendance_date = db.Column(
        db.Date,
        nullable=False,
        default=date.today
    )

    notes = db.Column(db.String(100))

    __table_args__ = (
        db.UniqueConstraint(
            "member_id",
            "attendance_date",
            name="uq_member_attendance"
        ),
    )