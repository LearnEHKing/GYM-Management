from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

import config
import backup
from models import GymOwner, MembershipPlan, OwnerPayment, db

admin_bp = Blueprint("admin", __name__)


def require_admin():
    if current_user.username != config.admin["username"]:
        abort(403)


@admin_bp.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    require_admin()
    return render_template("admin.html", active_page="admin", owners=GymOwner.query.order_by(GymOwner.join_date.desc()).all(), owner_payments=OwnerPayment.query.order_by(OwnerPayment.payment_date.desc()).all(), today=date.today(), owner_plans=config.plan)

@admin_bp.route("/admin/create_backup", methods=["GET"])
@login_required
def create_backup():
    require_admin()
    try :
        backup.create_backup()
        flash("New backup created.","success")
    except Exception as e:
        print(e)
        flash("ERROR : Couldn't create backup.","error")
    return redirect(url_for("admin.admin"))

@admin_bp.route("/admin/owners", methods=["POST"])
@login_required
def create_owner():
    require_admin()
    try:
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        plan_names = request.form.getlist("plan_name[]")
        plan_durations = request.form.getlist("plan_duration[]")
        plan_fees = request.form.getlist("plan_fee[]")
        trial_days = int(request.form["trial_days"])
        send_reminder = request.form["send_reminder"] == "True"
        join_date = datetime.strptime(request.form["join_date"], "%Y-%m-%d").date()
        if (not all((username, password, name, phone, plan_names, plan_durations, plan_fees))
                or len(password) < 8 or trial_days < 0):
            raise ValueError
        if GymOwner.query.filter_by(username=username).first():
            raise ValueError
        owner = GymOwner(username=username, password_hash=generate_password_hash(password), name=name, phone=phone,
                         join_date=join_date, trial_days=trial_days,send_reminder=send_reminder)
        db.session.add(owner)
        db.session.flush()
        for plan_name, duration, fee in zip(plan_names, plan_durations, plan_fees):
            db.session.add(MembershipPlan(owner_id=owner.id, name=plan_name, duration_months=int(duration), fee=int(fee)))
        db.session.commit()
        flash(f"Created the {name} owner profile.", "success")
    except (KeyError, ValueError):
        db.session.rollback()
        flash("Enter all required owner details and a password of at least 8 characters.", "error")
    return redirect(url_for("admin.admin"))


@admin_bp.route("/admin/owners/<int:owner_id>", methods=["POST"])
@login_required
def edit_owner(owner_id):
    require_admin()
    owner = GymOwner.query.get_or_404(owner_id)
    try:
        username = request.form.get("username", "").strip()
        duplicate = GymOwner.query.filter(GymOwner.username == username, GymOwner.id != owner.id).first()
        if not username or duplicate:
            raise ValueError
        owner.username, owner.name, owner.phone = username, request.form["name"].strip(), request.form["phone"].strip()
        owner.trial_days = int(request.form["trial_days"])
        if owner.trial_days < 0:
            raise ValueError
        owner.join_date = datetime.strptime(request.form["join_date"], "%Y-%m-%d").date()
        password = request.form.get("password", "")
        owner.send_reminder = request.form["send_reminder"] == "True"
        if password:
            if len(password) < 8:
                raise ValueError
            owner.password_hash = generate_password_hash(password)
        if not all((owner.name, owner.phone)):
            raise ValueError
        db.session.commit()
        flash(f"Updated {owner.name}.", "success")
    except (KeyError, ValueError):
        db.session.rollback()
        flash("Could not update the owner. Check all fields and ensure the username is unique.", "error")
    return redirect(url_for("admin.admin"))


@admin_bp.route("/admin/owner-payments", methods=["POST"])
@login_required
def create_owner_payment():
    require_admin()
    try:
        owner = GymOwner.query.get_or_404(int(request.form["owner_id"]))
        payment_date = datetime.strptime(request.form["payment_date"], "%Y-%m-%d").date()
        plan_name = request.form["plan_name"]
        selected_plan = config.plan.get(plan_name)
        if selected_plan is None:
            raise ValueError
        amount = int(selected_plan["fee"])
        owner.owner_plan = plan_name
        owner.payment_due_date = payment_date + timedelta(days=int(selected_plan["days"]))
        owner.member_limit_warning_plan = None
        db.session.add(OwnerPayment(owner_id=owner.id, amount=amount, payment_date=payment_date,
                                    plan_name=plan_name, remarks=request.form.get("remarks", "").strip() or None))
        db.session.commit()
        flash("Owner payment recorded.", "success")
    except (KeyError, TypeError, ValueError):
        db.session.rollback()
        flash("Enter valid owner payment details.", "error")
    return redirect(url_for("admin.admin"))
