from datetime import date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()
class GymOwner( UserMixin, db.Model):
    id = db.Column(db.Integer , primary_key=True)
    username  = db.Column(db.String(50), unique=True, nullable=False)
    password_hash  = db.Column(db.String(255),nullable=False)
    name = db.Column(db.String(100),nullable=False)
    phone  = db.Column(db.String(15),nullable=False)
    join_date  = db.Column(db.Date, default = date.today)
    payment_due_date = db.Column(db.Date)

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
    owner_id = db.Column(db.Integer, db.ForeignKey("gym_owner.id"), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Paid")
    payment_date = db.Column(db.Date, nullable=False, default=date.today)
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
    __table_args__ = (
    db.UniqueConstraint(
        "owner_id",
        "name",
        name="uq_owner_plan_name"
    ),
    )# Monthly, Quarterly...
    duration_months = db.Column(db.Integer, nullable=False)
    fee = db.Column(db.Integer, nullable=False)
    active = db.Column(db.Boolean, default=True)


class Member(db.Model):
    __tablename__ = "member"

    __table_args__ = (
        db.UniqueConstraint(
            "owner_id",
            "name",
            name="uq_owner_member_name"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("gym_owner.id"),
        nullable=False,
        index=True
    )
    payments = db.relationship(
        "Payment",
        backref="member",
        lazy=True,
        cascade="all, delete-orphan"
    )

    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(15),nullable=False)
    join_date = db.Column(db.Date,nullable=False)
    notes = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)
    current_plan = db.Column(db.String(50))
    membership_start = db.Column(db.Date)
    membership_expiry = db.Column(db.Date)

    @property
    def latest_payment(self):
        return (
            Payment.query
            .filter_by(member_id=self.id)
            .order_by(Payment.payment_date.desc(), Payment.id.desc())
            .first()
        )


class Payment(db.Model):
    __tablename__ = "payment"

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

    status = db.Column(db.String(20), nullable=False)

    remarks = db.Column(db.Text, default="")

    plan = db.relationship("MembershipPlan")