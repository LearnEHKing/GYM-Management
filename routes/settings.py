from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import MembershipPlan, db

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings")
@login_required
def settings():
    return render_template("settings.html", active_page="settings")


@settings_bp.route("/settings/plans", methods=["POST"])
@login_required
def create_plan():
    try:
        name = request.form["name"].strip()
        months = int(request.form["duration_months"])
        fee = int(request.form["fee"])
        if not name:
            flash("Plan name is required.", "error")
        elif months < 0 or fee < 0:
            flash("Invalid data.", "error")
        else:
            db.session.add(MembershipPlan(owner_id=current_user.id, name=name, duration_months=months, fee=fee))
            db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Server error! Please try again.", "error")
    return redirect(url_for("settings.settings"))
