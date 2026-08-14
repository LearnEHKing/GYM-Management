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

"""class Members( UserMixin, db.Model):
    id = db.Column(db.Integer , primary_key=True)
    username  = db.Column(db.String(50), unique=True, nullable=False)
    password_hash  = db.Column(db.String(255),nullable=False)
    name = db.Column(db.String(100),nullable=False)
    phone  = db.Column(db.String(15),nullable=False)
    join_date  = db.Column(db.Date, default = date.today)
    payment_due_date = db.Column(db.Date)
    plan  = db.Column(db.String(20),nullable=False)"""