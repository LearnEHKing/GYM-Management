import os
from werkzeug.security import generate_password_hash

from main import app
from models import GymOwner


def create_admin():
    admin_username = os.environ["ADMIN_USERNAME"]
    admin_password = os.environ["ADMIN_PASSWORD"]
    if GymOwner.query.filter_by(username=admin_username).first():
        print("Admin already exists.")
        return

    from models import db

    db.session.add(GymOwner(
            username=admin_username,
            password_hash=generate_password_hash(admin_password),
            name="Admin",
            phone="9876543210"
    ))
    db.session.commit()
    print("Admin created.")


if __name__ == "__main__":
    with app.app_context():
        create_admin()