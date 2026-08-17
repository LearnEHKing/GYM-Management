from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import MembershipPlan, db

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings")
@login_required
def settings():
    plans = MembershipPlan.query.filter_by(owner_id=current_user.id).order_by(
        MembershipPlan.active.desc(), MembershipPlan.duration_months, MembershipPlan.name
    ).all()
    return render_template("settings.html", active_page="settings", plans=plans)


@settings_bp.route("/settings/plans", methods=["POST"])
@login_required
def create_plan():
    try:
        name = request.form["name"].strip()
        months = int(request.form["duration_months"])
        fee = int(request.form["fee"])
        if not name:
            flash("Plan name is required.", "error")
        elif months < 1 or fee < 1:
            flash("Duration and fee must be greater than zero.", "error")
        else:
            db.session.add(MembershipPlan(owner_id=current_user.id, name=name, duration_months=months, fee=fee))
            db.session.commit()
            flash("Membership plan added.", "success")
    except Exception:
        db.session.rollback()
        flash("Could not save the plan. Plan names must be unique.", "error")
    return redirect(url_for("settings.settings"))


@settings_bp.route("/settings/plans/<int:plan_id>", methods=["POST"])
@login_required
def edit_plan(plan_id):
    plan = MembershipPlan.query.filter_by(id=plan_id, owner_id=current_user.id).first_or_404()
    try:
        name = request.form["name"].strip()
        months = int(request.form["duration_months"])
        fee = int(request.form["fee"])
        if not name or months < 1 or fee < 1:
            raise ValueError
        duplicate = MembershipPlan.query.filter(
            MembershipPlan.owner_id == current_user.id,
            MembershipPlan.name == name,
            MembershipPlan.id != plan.id,
        ).first()
        if duplicate:
            raise ValueError
        plan.name, plan.duration_months, plan.fee = name, months, fee
        db.session.commit()
        flash("Membership plan updated.", "success")
    except (KeyError, ValueError):
        db.session.rollback()
        flash("Enter a unique plan name, valid duration, and fee.", "error")
    return redirect(url_for("settings.settings"))


@settings_bp.route("/settings/plans/<int:plan_id>/status", methods=["POST"])
@login_required
def toggle_plan_status(plan_id):
    plan = MembershipPlan.query.filter_by(id=plan_id, owner_id=current_user.id).first_or_404()
    plan.active = not plan.active
    db.session.commit()
    flash(f"{plan.name} is now {'active' if plan.active else 'inactive'}.", "success")
    return redirect(url_for("settings.settings"))
