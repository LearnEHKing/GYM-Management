from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from models import GymOwner
from security import login_rate_limiter

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("members.index"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        ip_address = request.remote_addr or "unknown"
        if login_rate_limiter.is_limited(ip_address, username):
            error = "Too many login attempts. Please try again in a minute."
        else:
            owner = GymOwner.query.filter_by(username=username).first()
            if owner and check_password_hash(owner.password_hash, password):
                login_rate_limiter.reset_account(ip_address, username)
                login_user(owner,remember=True)
                return redirect(url_for("members.index"))
            login_rate_limiter.register_failure(ip_address, username)
            error = "Invalid username or password."
    return render_template("login.html", error=error)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("members.index"))
