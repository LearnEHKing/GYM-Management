from flask import Flask
from flask_login import LoginManager

from scheduler import init_scheduler
from models import GymOwner, db


def create_app():
    app = Flask(__name__)
    app.secret_key = "ppp"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///gym.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    init_scheduler(app)
    
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(GymOwner, int(user_id))

    from routes.admin import admin_bp
    from routes.auth import auth_bp
    from routes.members import members_bp
    from routes.settings import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(admin_bp)
    return app


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
