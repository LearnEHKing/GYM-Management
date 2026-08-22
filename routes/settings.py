from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash

from models import EditHistory, MembershipPlan, db
from services.edit_history import record_edit
from observability import report_unexpected_error
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from services.phone import normalize_phone

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings")
@login_required
def settings():
    return render_template("settings.html", active_page="settings")


@settings_bp.route("/settings/membership-plans")
@login_required
def membership_plans():
    plans = MembershipPlan.query.filter_by(owner_id=current_user.id).order_by(
        MembershipPlan.active.desc(), MembershipPlan.duration_months, MembershipPlan.name
    ).all()
    plan_history = EditHistory.query.filter_by(
        owner_id=current_user.id, entity_type="membership_plan"
    ).filter(EditHistory.entity_id.in_([plan.id for plan in plans])).order_by(
        EditHistory.created_at.desc(), EditHistory.id.desc()
    ).all() if plans else []
    history_by_plan = {}
    for entry in plan_history:
        history_by_plan.setdefault(entry.entity_id, []).append(entry)
    return render_template("membership_plans.html", active_page="settings", plans=plans,
                           history_by_plan=history_by_plan)


@settings_bp.route("/settings/profile", methods=["POST"])
@login_required
def update_profile():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    try:
        phone = normalize_phone(phone)
    except ValueError:
        phone = ""
    if not name:
        flash("Gym name is required.", "error")
    elif not phone:
        flash("Enter a valid Indian mobile number.", "error")
    else:
        current_user.name = name[:100]
        current_user.phone = phone
        db.session.commit()
        flash("Gym profile updated.", "success")
    return redirect(url_for("settings.settings"))


@settings_bp.route("/settings/member-defaults", methods=["POST"])
@login_required
def update_member_defaults():
    try:
        trial_days = int(request.form.get("trial_days", 0))
        inactive_member_removal_days = int(request.form.get("inactive_member_removal_days", 30))
        membership_removal_policy = request.form.get(
            "membership_removal_policy", current_user.membership_removal_policy
        )
        if (trial_days < 0 or trial_days > 365 or inactive_member_removal_days < 1
                or inactive_member_removal_days > 3650
                or membership_removal_policy not in {"expire", "pause"}):
            raise ValueError
        current_user.trial_days = trial_days
        current_user.inactive_member_removal_days = inactive_member_removal_days
        current_user.membership_removal_policy = membership_removal_policy
        db.session.commit()
        flash("Member defaults updated.", "success")
    except ValueError:
        flash("Trial days must be between 0 and 365, and the inactivity limit between 1 and 3650 days.", "error")
    return redirect(url_for("settings.settings"))


@settings_bp.route("/settings/password", methods=["POST"])
@login_required
def update_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")
    if not check_password_hash(current_user.password_hash, current_password):
        flash("Your current password is incorrect.", "error")
    elif len(new_password) < 8:
        flash("Your new password must contain at least 8 characters.", "error")
    elif new_password != confirm_password:
        flash("New password and confirmation do not match.", "error")
    else:
        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash("Password updated.", "success")
    return redirect(url_for("settings.settings"))


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
    except (KeyError, TypeError, ValueError, IntegrityError):
        db.session.rollback()
        flash("Could not save the plan. Plan names must be unique.", "error")
    except SQLAlchemyError as error:
        db.session.rollback()
        report_unexpected_error(error, "settings.create_plan")
        flash("Could not save the plan right now.", "error")
    return redirect(url_for("settings.membership_plans"))


@settings_bp.route("/settings/plans/<int:plan_id>", methods=["POST"])
@login_required
def edit_plan(plan_id):
    plan = MembershipPlan.query.filter_by(id=plan_id, owner_id=current_user.id).first_or_404()
    try:
        reason = request.form.get("edit_reason", "").strip()
        if not 3 <= len(reason) <= 500:
            raise ValueError
        before_data = {"name": plan.name, "duration_months": plan.duration_months,
                       "fee": plan.fee, "active": plan.active}
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
        record_edit(plan.owner_id, current_user.id, current_user.username, "membership_plan", plan.id, "updated", reason,
                before_data, {"name": plan.name, "duration_months": plan.duration_months,
                       "fee": plan.fee, "active": plan.active}, context_id=plan.owner_id)
        db.session.commit()
        flash("Membership plan updated.", "success")
    except (KeyError, ValueError):
        db.session.rollback()
        flash("Enter a unique plan name, valid duration, fee, and edit reason (3 to 500 characters).", "error")
    return redirect(url_for("settings.membership_plans"))


@settings_bp.route("/settings/plans/<int:plan_id>/status", methods=["POST"])
@login_required
def toggle_plan_status(plan_id):
    plan = MembershipPlan.query.filter_by(id=plan_id, owner_id=current_user.id).first_or_404()
    reason = request.form.get("edit_reason", "").strip()
    if not 3 <= len(reason) <= 500:
        flash("A reason is required (3 to 500 characters).", "error")
        return redirect(url_for("settings.membership_plans"))
    before_data = {"name": plan.name, "duration_months": plan.duration_months,
                   "fee": plan.fee, "active": plan.active}
    plan.active = not plan.active
    record_edit(plan.owner_id, current_user.id, current_user.username, "membership_plan", plan.id, "status_changed", reason,
                before_data, {"name": plan.name, "duration_months": plan.duration_months,
                               "fee": plan.fee, "active": plan.active}, context_id=plan.owner_id)
    db.session.commit()
    flash(f"{plan.name} is now {'active' if plan.active else 'inactive'}.", "success")
    return redirect(url_for("settings.membership_plans"))
