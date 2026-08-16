from datetime import date
from werkzeug.security import generate_password_hash
from main import app
from models import db, GymOwner

with app.app_context():
    db.create_all()

    if not GymOwner.query.filter_by(username="admin").first():
        db.session.add(GymOwner(
            username="admin",
            password_hash=generate_password_hash("pppp"),
            name="Admin",
            phone="9876543210",
            payment_due_date=date(2027, 8, 16)
        ))
        db.session.commit()
        print("Admin created.")
    else:
        print("Admin already exists.")