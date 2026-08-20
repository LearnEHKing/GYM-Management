import os
from datetime import date
from werkzeug.security import generate_password_hash
from main import app
from models import db, GymOwner

with app.app_context():
    db.create_all()

    admin_username = os.environ["ADMIN_USERNAME"]
    admin_password = os.environ["ADMIN_PASSWORD"]
    if not GymOwner.query.filter_by(username=admin_username).first():
        db.session.add(GymOwner(
            username=admin_username,
            password_hash=generate_password_hash(admin_password),
            name="Admin",
            phone="9876543210",
            payment_due_date=date(2027, 8, 16)
        ))
        db.session.commit()
        print("Admin created.")
    else:
        print("Admin already exists.")