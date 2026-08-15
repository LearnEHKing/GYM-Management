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
    plan  = db.Column(db.String(20),nullable=False)

    members = db.relationship("Member",backref="owner", lazy=True)

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
        nullable=False
    )

    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(15),nullable=False)
    join_date = db.Column(db.Date,nullable=False)
    notes = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)


class Payment(db.Model):
    __tablename__ = "payment"

    id = db.Column(db.Integer, primary_key=True)

    member_id = db.Column(
        db.Integer,
        db.ForeignKey("member.id"),
        nullable=False
    )

    # Membership
    plan_name = db.Column(db.String(50), nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)

    # Money
    amount = db.Column(db.Integer, nullable=False)
    amount_paid = db.Column(db.Integer, default=0)

    # Dates
    payment_date = db.Column(db.Date, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)

    # Paid / Partial / Unpaid
    status = db.Column(db.String(20), nullable=False)

    remarks = db.Column(db.Text)

    member = db.relationship("Member", backref="payments")
