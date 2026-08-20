"""
Creates 8 realistic demo gyms.

Run:
    python fake_data.py

Logins:
    demo_gym1 / value of DEMO_PASSWORD
    demo_gym2 / value of DEMO_PASSWORD
    ...
    demo_gym8 / value of DEMO_PASSWORD
"""

from datetime import date, datetime, time
import os
import random

from dateutil.relativedelta import relativedelta
from werkzeug.security import generate_password_hash

from main import app
from models import Attendance, GymOwner, Member, Membership, MembershipPlan, db
from services.memberships import new_membership


DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD")
if not DEMO_PASSWORD:
    raise RuntimeError("DEMO_PASSWORD must be set when creating demo data.")

GYMS = [
    ("demo_gym1", "Iron House Demo 1", 15),
    ("demo_gym2", "Iron House Demo 2", 7),
    ("demo_gym3", "Iron House Demo 3", 1),
    ("demo_gym4", "Iron House Demo 4", -2),   # Already expired
    ("demo_gym5", "Iron House Demo 5", 25),
    ("demo_gym6", "Iron House Demo 6", 40),
    ("demo_gym7", "Iron House Demo 7", 60),
    ("demo_gym8", "Iron House Demo 8", 90),
]
random.seed(20260817)

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Arjun", "Kabir", "Rohan", "Rahul", "Amit",
    "Ishaan", "Karan", "Sanjay", "Manish", "Priya", "Ananya", "Kavya", "Neha",
    "Pooja", "Sneha", "Riya", "Aditi", "Meera", "Nisha", "Sakshi", "Divya",
]
LAST_NAMES = [
    "Sharma", "Verma", "Singh", "Gupta", "Yadav", "Patel", "Kumar", "Mishra",
    "Jain", "Sinha", "Chauhan", "Das",
]
AREAS = ["Sector 4", "Civil Lines", "Shastri Nagar", "Gandhi Road", "Model Town", "Station Road"]


def make_check_in(day):
    hour = random.choices([5, 6, 7, 8, 17, 18, 19], weights=[16, 22, 20, 12, 7, 12, 11])[0]
    return datetime.combine(day, time(hour, random.randint(0, 58), random.randint(0, 59)))


def seed_demo_gym():
    db.create_all()
    for username, gym_name, due_days in GYMS:
        if GymOwner.query.filter_by(username=username).first():
            print(f"{username} already exists.")
            continue
    
        today = date.today()
        owner = GymOwner(
            username=username,
            password_hash=generate_password_hash(DEMO_PASSWORD),
            name=gym_name,
            phone=f"9{random.randint(100000000, 999999999)}",
            join_date=today - relativedelta(months=random.randint(3, 18)),
            payment_due_date=today + relativedelta(days=due_days),
            trial_days=3,
        )
        db.session.add(owner)
        db.session.flush()
    
        plan_specs = [("Monthly", 1, 1200), ("Quarterly", 3, 3200), ("Half Yearly", 6, 5800), ("Annual", 12, 10500)]
        plans = {}
        for name, months, fee in plan_specs:
            plan = MembershipPlan(owner_id=owner.id, name=name, duration_months=months, fee=fee)
            db.session.add(plan)
            plans[name] = plan
        db.session.flush()
    
        member_count = random.randint(45, 95)

        for index in range(member_count):
            name = f"{FIRST_NAMES[index % len(FIRST_NAMES)]} {LAST_NAMES[index // len(FIRST_NAMES)]}"
            joined = today - relativedelta(days=random.randint(8, 360))
            member = Member(
                owner_id=owner.id,
                name=name,
                phone=f"9{random.randint(100000000, 999999999)}",
                address=f"{random.randint(1, 99)}, {random.choice(AREAS)}",
                join_date=joined,
                notes=random.choice(["", "Morning batch", "Strength training", "Weight-loss goal"]),
                membership_active=True,
            )
            db.session.add(member)
            db.session.flush()
    
            # Give long-standing members a genuine payment history before their current plan.
            if joined < today - relativedelta(months=3):
                old_plan = plans["Monthly"]
                old_payment_day = joined + relativedelta(days=3)
                old_expiry = old_payment_day + relativedelta(months=old_plan.duration_months) - relativedelta(days=1)
                db.session.add(Membership(
                    member_id=member.id, plan_id=old_plan.id, plan_name=old_plan.name,
                    duration_months=old_plan.duration_months, fee=old_plan.fee, amount_paid=old_plan.fee,
                    payment_date=old_payment_day, start_date=old_payment_day, expiry_date=old_expiry,
                    remarks="Demo payment history",
                ))
    
            plan = random.choices(
                [plans["Monthly"], plans["Quarterly"], plans["Half Yearly"], plans["Annual"]],
                weights=[45, 30, 15, 10],
            )[0]
            payment_day = max(joined, today - relativedelta(days=random.randint(0, 80)))
            new_membership(member, plan, plan.fee, payment_day, "Demo membership")
            if index in {3, 14, 25, 36}:
                member.membership_expiry = today + relativedelta(days=2)
            
            elif index >= member_count - 6:
                member.membership_expiry = today - relativedelta(days=random.randint(1, 25))
                member.membership_active = False
    
            # Attendance spans 90 days and has a realistic, varied frequency.
            attendance_start = max(joined, today - relativedelta(days=89))
            day = attendance_start
            while day <= today:
                if random.random() < (0.44 if member.membership_active else 0.12):
                    db.session.add(Attendance(member_id=member.id, attendance_date=day, check_in=make_check_in(day)))
                day += relativedelta(days=1)

    db.session.commit()
    for username, _, _ in GYMS:
        print(f"{username} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    with app.app_context():
        try:
            seed_demo_gym()
        except Exception:
            db.session.rollback()
            raise
