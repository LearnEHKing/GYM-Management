from datetime import date, timedelta
import os
import uuid

from flask import Flask, g, jsonify, redirect, request, url_for
from flask_login import LoginManager, current_user, logout_user
from flask_migrate import Migrate
from sqlalchemy import text
from werkzeug.middleware.proxy_fix import ProxyFix

import config
from scheduler import init_scheduler, scheduler
from models import GymOwner, db, local_today
from config import required_env
from observability import (
    begin_request,
    configure_logging,
    metrics_snapshot,
    record_request,
    report_unexpected_error,
)
from security import csrf_token, validate_csrf_request


migrate = Migrate()


def create_app():
    app = Flask(__name__)
    running_flask_cli = os.environ.get("FLASK_RUN_FROM_CLI") == "true"
    configure_logging()
    app.secret_key = required_env("APP_SECRET_KEY")
    app.config["SQLALCHEMY_DATABASE_URI"] = required_env("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    cookie_secure = os.environ.get("SESSION_COOKIE_SECURE", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }
    app.config.update(
        SESSION_COOKIE_SECURE=cookie_secure,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_SECURE=cookie_secure,
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
    migrate.init_app(app, db)

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def observe_request():
        g.request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
        g.request_method = request.method
        g.request_path = request.path
        begin_request()

    @app.after_request
    def finish_request(response):
        record_request(response.status_code)
        response.headers["X-Request-ID"] = g.request_id
        return response

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/ready")
    def ready():
        try:
            db.session.execute(text("SELECT 1"))
            if not scheduler.running:
                raise RuntimeError("scheduler is not running")
        except Exception:
            db.session.rollback()
            return jsonify({"status": "not_ready"}), 503
        return jsonify({"status": "ready"})

    @app.get("/metrics")
    def metrics():
        return jsonify(metrics_snapshot())

    @app.errorhandler(500)
    def handle_internal_error(error):
        report_unexpected_error(error, "http.internal_server_error")
        return jsonify({"error": "Internal server error"}), 500

    @app.before_request
    def protect_unsafe_requests():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            validate_csrf_request()

    @app.before_request
    def require_active_subscription():
        owner_endpoint = request.endpoint and request.endpoint.split(".", 1)[0]
        if (current_user.is_authenticated and owner_endpoint in {"members", "settings"}
            and current_user.username != config.admin["username"]
            and request.endpoint != "members.plan_over"
            and (not current_user.payment_due_date or current_user.payment_due_date < local_today())):
            logout_user()
            return redirect(url_for("members.plan_over"))

    if not running_flask_cli:
        with app.app_context():
            try:
                db.session.execute(text("SELECT 1 FROM gym_owner LIMIT 1"))
            except Exception as error:
                db.session.rollback()
                raise RuntimeError(
                    "Database schema is unavailable or not migrated. "
                    "Run 'flask --app main db upgrade' before starting the application."
                ) from error

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
    app.run(host="0.0.0.0",port=5000,debug=True)
