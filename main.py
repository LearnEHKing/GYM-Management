from datetime import date, timedelta
import os

from flask import Flask, redirect, request, url_for
from flask_login import LoginManager, current_user
from sqlalchemy import inspect, text
from werkzeug.middleware.proxy_fix import ProxyFix

from scheduler import init_scheduler
from models import GymOwner, db
from config import required_env
from security import csrf_token, validate_csrf_request


def create_app():
    app = Flask(__name__)
    app.secret_key = required_env("APP_SECRET_KEY")
    app.config["SQLALCHEMY_DATABASE_URI"] = required_env("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_SECURE=True,
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_DURATION=timedelta(days=30),
        REMEMBER_COOKIE_REFRESH_EACH_REQUEST=True,
    )
    trusted_proxy_hops = int(os.environ.get("TRUSTED_PROXY_HOPS", "0"))
    if trusted_proxy_hops < 0:
        raise RuntimeError("TRUSTED_PROXY_HOPS must be zero or greater.")
    if trusted_proxy_hops:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=trusted_proxy_hops,
            x_proto=trusted_proxy_hops,
            x_host=trusted_proxy_hops,
        )
    db.init_app(app)

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def protect_unsafe_requests():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            validate_csrf_request()

    @app.before_request
    def require_active_subscription():
        owner_endpoint = request.endpoint and request.endpoint.split(".", 1)[0]
        if (current_user.is_authenticated and owner_endpoint in {"members", "settings"}
                and request.endpoint not in {"members.index", "members.plan_over"}
                and (not current_user.payment_due_date or current_user.payment_due_date < date.today())):
            return redirect(url_for("members.plan_over"))

    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        owner_columns = {column["name"] for column in inspector.get_columns("gym_owner")}
        if "owner_plan" not in owner_columns:
            db.session.execute(text("ALTER TABLE gym_owner ADD COLUMN owner_plan VARCHAR(50)"))
        if "member_limit_warning_plan" not in owner_columns:
            db.session.execute(text("ALTER TABLE gym_owner ADD COLUMN member_limit_warning_plan VARCHAR(50)"))
        if "inactive_member_removal_days" not in owner_columns:
            db.session.execute(
                text("ALTER TABLE gym_owner ADD COLUMN inactive_member_removal_days INTEGER NOT NULL DEFAULT 30")
            )
        payment_columns = {column["name"] for column in inspector.get_columns("owner_payment")}
        if "plan_name" not in payment_columns:
            db.session.execute(text("ALTER TABLE owner_payment ADD COLUMN plan_name VARCHAR(50)"))
        history_columns = {column["name"] for column in inspector.get_columns("edit_history")}
        if "actor_name" not in history_columns:
            db.session.execute(text("ALTER TABLE edit_history ADD COLUMN actor_name VARCHAR(100)"))
        if "context_id" not in history_columns:
            db.session.execute(text("ALTER TABLE edit_history ADD COLUMN context_id INTEGER"))
        db.session.commit()

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
    app.run()
