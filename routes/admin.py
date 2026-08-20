from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from werkzeug.security import generate_password_hash

import config
import backup
from models import EditHistory, GymOwner, Member, MembershipPlan, OwnerPayment, db
from services.edit_history import record_edit

admin_bp = Blueprint("admin", __name__)


def require_admin():
    if current_user.username != config.admin["username"]:
        abort(403)


def refresh_owner_subscription(owner):
    """Keep a gym's current subscription aligned with its newest payment."""
    latest_payment = OwnerPayment.query.filter_by(owner_id=owner.id).order_by(
        OwnerPayment.payment_date.desc(), OwnerPayment.id.desc()
    ).first()
    if latest_payment and latest_payment.plan_name in config.plan:
        plan = config.plan[latest_payment.plan_name]
        owner.owner_plan = latest_payment.plan_name
        owner.payment_due_date = latest_payment.payment_date + timedelta(days=int(plan["days"]))
    else:
        owner.owner_plan = None
        owner.payment_due_date = None
    owner.member_limit_warning_plan = None


@admin_bp.route("/admin")
@login_required
def admin():
    require_admin()
    today = date.today()
    month_start = today.replace(day=1)
    owners = GymOwner.query.order_by(GymOwner.name.asc()).all()
    active_subscriptions = GymOwner.query.filter(GymOwner.payment_due_date >= today).count()
    total_members = db.session.query(func.count(Member.id)).scalar() or 0
    monthly_revenue = db.session.query(func.sum(OwnerPayment.amount)).filter(
        OwnerPayment.payment_date >= month_start, OwnerPayment.payment_date <= today
    ).scalar() or 0
    return render_template("admin.html", active_page="admin_gyms", owners=owners, today=today,
                           active_subscriptions=active_subscriptions, total_members=total_members,
                           monthly_revenue=monthly_revenue)


@admin_bp.route("/admin/gyms/new")
@login_required
def add_gym():
    require_admin()
    return render_template("admin_add_gym.html", active_page="admin_add_gym", today=date.today())


@admin_bp.route("/admin/gym_details/<int:gym_id>")
@login_required
def gym_details(gym_id):
    require_admin()
    owner = GymOwner.query.get_or_404(gym_id)
    payments = OwnerPayment.query.filter_by(owner_id=owner.id).order_by(
        OwnerPayment.payment_date.desc(), OwnerPayment.id.desc()
    ).all()
    payment_history = EditHistory.query.filter_by(
        owner_id=owner.id, entity_type="owner_payment"
    ).order_by(EditHistory.created_at.desc(), EditHistory.id.desc()).all()
    history_by_payment = {}
    for entry in payment_history:
        history_by_payment.setdefault(entry.entity_id, []).append(entry)
    deleted_payment_history = [entry for entry in payment_history if entry.action == "deleted"]
    members_count = Member.query.filter_by(owner_id=owner.id).count()
    active_members = Member.query.filter_by(owner_id=owner.id, membership_active=True).count()
    return render_template("admin_gym_details.html", active_page="admin_gyms", owner=owner,
                           payments=payments, members_count=members_count,
                           active_members=active_members, today=date.today(), owner_plans=config.plan,
                           history_by_payment=history_by_payment,
                           deleted_payment_history=deleted_payment_history)


@admin_bp.route("/admin/payments")
@login_required
def payments():
    require_admin()
    owner_payments = OwnerPayment.query.order_by(OwnerPayment.payment_date.desc(), OwnerPayment.id.desc()).all()
    return render_template("admin_payments.html", active_page="admin_payments", owner_payments=owner_payments)


@admin_bp.route("/admin/settings", methods=["GET", "POST"])
@login_required
def settings():
    require_admin()
    if request.method == "POST":
        try:
            reminder_days = [int(day.strip()) for day in request.form["membership_reminder_days"].split(",") if day.strip()]
            message_limit = int(request.form["daily_message_limit"])
            warning_delta = int(request.form["plan_delta_members_before_warning"])
            if not reminder_days or any(day < 0 for day in reminder_days) or message_limit < 0 or warning_delta < 0:
                raise ValueError
            config.update_runtime_settings(sorted(set(reminder_days), reverse=True), message_limit, warning_delta)
            flash("Admin settings saved.", "success")
        except (KeyError, TypeError, ValueError):
            flash("Use non-negative numbers. Separate reminder days with commas.", "error")
        return redirect(url_for("admin.settings"))
    return render_template("admin_settings.html", active_page="admin_settings", config=config)

@admin_bp.route("/admin/create_backup", methods=["POST"])
@login_required
def create_backup():
    require_admin()
    try :
        backup.create_backup()
        flash("New backup created.","success")
    except Exception as e:
        print(e)
        flash("ERROR : Couldn't create backup.","error")
    return redirect(url_for("admin.settings") if request.args.get("return_to") == "settings" else url_for("admin.admin"))

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
        send_reminder = request.form.get("send_reminder") == "True"
        join_date = datetime.strptime(request.form["join_date"], "%Y-%m-%d").date()
        if (not all((username, password, name, phone, plan_names, plan_durations, plan_fees))
                or len(password) < 8 or trial_days < 0
                or len(plan_names) != len(plan_durations) or len(plan_names) != len(plan_fees)
                or len(plan_names) > 20):
            raise ValueError
        if GymOwner.query.filter_by(username=username).first():
            raise ValueError
        validated_plans = []
        for plan_name, duration, fee in zip(plan_names, plan_durations, plan_fees):
            plan_name = plan_name.strip()
            duration = int(duration)
            fee = int(fee)
            if not plan_name or len(plan_name) > 50 or duration < 1 or duration > 120 or fee < 1:
                raise ValueError
            validated_plans.append((plan_name, duration, fee))
        owner = GymOwner(username=username, password_hash=generate_password_hash(password), name=name, phone=phone,
                         join_date=join_date, trial_days=trial_days,send_reminder=send_reminder)
        db.session.add(owner)
        db.session.flush()
        for plan_name, duration, fee in validated_plans:
            db.session.add(MembershipPlan(owner_id=owner.id, name=plan_name, duration_months=duration, fee=fee))
        db.session.commit()
        flash(f"Created the {name} gym profile.", "success")
    except (KeyError, ValueError):
        db.session.rollback()
        flash("Enter all required owner details and a password of at least 8 characters.", "error")
    return redirect(url_for("admin.gym_details", gym_id=owner.id) if 'owner' in locals() else url_for("admin.add_gym"))


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
        owner.send_reminder = request.form.get("send_reminder") == "True"
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
    return redirect(url_for("admin.gym_details", gym_id=owner.id))


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
    return redirect(url_for("admin.gym_details", gym_id=request.form.get("owner_id", type=int)) if request.form.get("owner_id", type=int) else url_for("admin.payments"))


@admin_bp.route("/admin/owner-payments/<int:payment_id>", methods=["POST"])
@login_required
def edit_owner_payment(payment_id):
    require_admin()
    payment = OwnerPayment.query.get_or_404(payment_id)
    try:
        reason = request.form.get("edit_reason", "").strip()
        if not 3 <= len(reason) <= 500:
            raise ValueError
        before_data = {
            "plan_name": payment.plan_name,
            "amount": payment.amount,
            "payment_date": payment.payment_date.isoformat(),
            "remarks": payment.remarks,
        }
        plan_name = request.form["plan_name"]
        if plan_name not in config.plan:
            raise ValueError
        payment.plan_name = plan_name
        payment.amount = int(config.plan[plan_name]["fee"])
        payment.payment_date = datetime.strptime(request.form["payment_date"], "%Y-%m-%d").date()
        payment.remarks = request.form.get("remarks", "").strip() or None
        record_edit(payment.owner_id, current_user.id, current_user.username, "owner_payment", payment.id, "updated", reason,
                before_data, {"plan_name": payment.plan_name, "amount": payment.amount,
                       "payment_date": payment.payment_date.isoformat(), "remarks": payment.remarks},
                context_id=payment.owner_id)
        refresh_owner_subscription(payment.owner)
        db.session.commit()
        flash("Payment updated.", "success")
    except (KeyError, TypeError, ValueError):
        db.session.rollback()
        flash("Enter valid payment details.", "error")
    return redirect(url_for("admin.gym_details", gym_id=payment.owner_id))


@admin_bp.route("/admin/owner-payments/<int:payment_id>/delete", methods=["POST"])
@login_required
def delete_owner_payment(payment_id):
    require_admin()
    payment = OwnerPayment.query.get_or_404(payment_id)
    owner = payment.owner
    gym_id = owner.id
    reason = request.form.get("edit_reason", "").strip()
    if not 3 <= len(reason) <= 500:
        flash("A deletion reason is required (3 to 500 characters).", "error")
        return redirect(url_for("admin.gym_details", gym_id=gym_id))
    record_edit(owner.id, current_user.id, current_user.username, "owner_payment", payment.id, "deleted", reason, {
        "plan_name": payment.plan_name,
        "amount": payment.amount,
        "payment_date": payment.payment_date.isoformat(),
        "remarks": payment.remarks,
    }, None, context_id=owner.id)
    db.session.delete(payment)
    db.session.flush()
    refresh_owner_subscription(owner)
    db.session.commit()
    flash("Payment deleted.", "success")
    return redirect(url_for("admin.gym_details", gym_id=gym_id))
