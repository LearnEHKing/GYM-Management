from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from models import GymOwner

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("members.index"))
    error = None
    if request.method == "POST":
        owner = GymOwner.query.filter_by(username=request.form["username"]).first()
        if owner and check_password_hash(owner.password_hash, request.form["password"]):
            login_user(owner)
            return redirect(url_for("members.index"))
        error = "Invalid username or password."
    return render_template("login.html", error=error)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("members.index"))
