from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from werkzeug.security import generate_password_hash

import config
import backup
from models import EditHistory, GymOwner, Member, MembershipPlan, OwnerPayment, db, local_today
from services.edit_history import record_edit
from observability import report_unexpected_error
from services.phone import normalize_phone
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

admin_bp = Blueprint("admin", __name__)


def require_admin():
    if current_user.username != config.admin["username"]:
        abort(403)


def plan_total(plan):
    return int(plan["fee"]) + int(plan.get("whatsapp_fee", 0))


def refresh_owner_subscription(owner):
    """Keep a gym's current subscription aligned with its newest payment."""
    latest_payment = OwnerPayment.query.filter_by(owner_id=owner.id).order_by(
        OwnerPayment.payment_date.desc(), OwnerPayment.id.desc()
    ).first()
    if latest_payment and latest_payment.plan_name in config.plan:
        plan = config.plan[latest_payment.plan_name]
        owner.owner_plan = latest_payment.plan_name
        subscription_start = latest_payment.subscription_start_date or latest_payment.payment_date
        owner.payment_due_date = subscription_start + timedelta(days=int(plan["days"]))
    else:
        owner.owner_plan = None
        owner.payment_due_date = None
    owner.member_limit_warning_plan = None


@admin_bp.route("/admin")
@login_required
def admin():
    require_admin()
    today = local_today()
    month_start = today.replace(day=1)
    page = request.args.get("page", 1, type=int)
    owner_pagination = GymOwner.query.order_by(GymOwner.name.asc()).paginate(
        page=page, per_page=100, error_out=False
    )
    active_subscriptions = GymOwner.query.filter(GymOwner.payment_due_date >= today).count()
    total_members = db.session.query(func.count(Member.id)).scalar() or 0
    monthly_revenue = db.session.query(func.sum(OwnerPayment.amount)).filter(
        OwnerPayment.payment_date >= month_start, OwnerPayment.payment_date <= today
    ).scalar() or 0
    return render_template("admin.html", active_page="admin_gyms", owners=owner_pagination.items,
                           owner_pagination=owner_pagination, owners_total=owner_pagination.total, today=today,
                           active_subscriptions=active_subscriptions, total_members=total_members,
                           monthly_revenue=monthly_revenue)


@admin_bp.route("/admin/gyms/new")
@login_required
def add_gym():
    require_admin()
    return render_template("admin_add_gym.html", active_page="admin_add_gym", today=local_today())


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
    current_plan = config.plan.get(owner.owner_plan)
    current_plan_total = plan_total(current_plan) if current_plan else 0
    upgrade_plans = {
        name: details for name, details in config.plan.items()
        if current_plan and int(details["member_allowed"]) > int(current_plan["member_allowed"])
    }
    members_count = Member.query.filter_by(owner_id=owner.id).count()
    active_members = Member.query.filter_by(owner_id=owner.id, membership_active=True).count()
    return render_template("admin_gym_details.html", active_page="admin_gyms", owner=owner,
                           payments=payments, members_count=members_count,
                           active_members=active_members, today=local_today(), owner_plans=config.plan,
                           history_by_payment=history_by_payment,
                           deleted_payment_history=deleted_payment_history,
                           current_plan_total=current_plan_total, upgrade_plans=upgrade_plans)


@admin_bp.route("/admin/payments")
@login_required
def payments():
    require_admin()
    page = request.args.get("page", 1, type=int)
    payment_pagination = OwnerPayment.query.order_by(
        OwnerPayment.payment_date.desc(), OwnerPayment.id.desc()
    ).paginate(page=page, per_page=100, error_out=False)
    return render_template(
        "admin_payments.html", active_page="admin_payments",
        owner_payments=payment_pagination.items, payment_pagination=payment_pagination
    )


@admin_bp.route("/admin/settings", methods=["GET", "POST"])
@login_required
def settings():
    require_admin()
    if request.method == "POST":
        try:
            reminder_days = [int(day.strip()) for day in request.form["membership_reminder_days"].split(",") if day.strip()]
            owner_reminder_days = [int(day.strip()) for day in request.form["owner_subscription_reminder_days"].split(",") if day.strip()]
            message_limit = int(request.form["daily_message_limit"])
            warning_delta = int(request.form["plan_delta_members_before_warning"])
            if (not reminder_days or not owner_reminder_days
                    or any(day < 0 for day in reminder_days + owner_reminder_days)
                    or message_limit < 0 or warning_delta < 0):
                raise ValueError
            config.update_runtime_settings(
                sorted(set(reminder_days), reverse=True),
                sorted(set(owner_reminder_days), reverse=True),
                message_limit, warning_delta,
            )
            flash("Admin settings saved.", "success")
        except (KeyError, TypeError, ValueError, RuntimeError):
            flash("Use non-negative numbers. Separate both reminder-day lists with commas.", "error")
        return redirect(url_for("admin.settings"))
    return render_template("admin_settings.html", active_page="admin_settings", config=config)

@admin_bp.route("/admin/create_backup", methods=["POST"])
@login_required
def create_backup():
    require_admin()
    try :
        backup.create_backup()
        flash("New backup created.","success")
    except (OSError, RuntimeError, ValueError) as error:
        db.session.rollback()
        report_unexpected_error(error, "admin.create_backup")
        flash(f"Backup failed: {error}", "error")
    return redirect(url_for("admin.settings") if request.args.get("return_to") == "settings" else url_for("admin.admin"))

@admin_bp.route("/admin/owners", methods=["POST"])
@login_required
def create_owner():
    require_admin()
    owner = None
    try:
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        name = request.form.get("name", "").strip()
        phone = normalize_phone(request.form.get("phone", ""))
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
            raise ValueError("Complete all owner fields, use a password of at least 8 characters, and add valid plans.")
        if GymOwner.query.filter_by(username=username).first():
            raise ValueError("That username is already in use.")
        validated_plans = []
        plan_names_seen = set()
        for plan_name, duration, fee in zip(plan_names, plan_durations, plan_fees):
            plan_name = plan_name.strip()
            duration = int(duration)
            fee = int(fee)
            normalized_plan_name = plan_name.casefold()
            if (not plan_name or len(plan_name) > 30 or duration < 1 or duration > 120 or fee < 1
                    or normalized_plan_name in plan_names_seen):
                raise ValueError("Plan names must be unique and 1-30 characters; duration and fee must be positive.")
            plan_names_seen.add(normalized_plan_name)
            validated_plans.append((plan_name, duration, fee))
        owner = GymOwner(username=username, password_hash=generate_password_hash(password), name=name, phone=phone,
                         join_date=join_date, trial_days=trial_days,send_reminder=send_reminder)
        db.session.add(owner)
        db.session.flush()
        for plan_name, duration, fee in validated_plans:
            db.session.add(MembershipPlan(owner_id=owner.id, name=plan_name, duration_months=duration, fee=fee))
        db.session.commit()
        flash(f"Created the {name} gym profile.", "success")
    except ValueError as error:
        db.session.rollback()
        message = str(error) or "Enter all required owner details and valid membership plans."
        if message == "1":
            message = "Enter all required owner details and valid membership plans."
        flash(message, "error")
        return render_template("admin_add_gym.html", active_page="admin_add_gym", today=local_today())
    except IntegrityError as error:
        db.session.rollback()
        report_unexpected_error(error, "admin.create_owner.integrity")
        flash("Could not create the gym owner. The username or a plan name may already exist.", "error")
        return render_template("admin_add_gym.html", active_page="admin_add_gym", today=local_today())
    except SQLAlchemyError as error:
        db.session.rollback()
        report_unexpected_error(error, "admin.create_owner")
        flash("Could not create the gym owner right now.", "error")
        return render_template("admin_add_gym.html", active_page="admin_add_gym", today=local_today())
    return redirect(url_for("admin.gym_details", gym_id=owner.id))


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
        owner.username, owner.name = username, request.form["name"].strip()
        owner.phone = normalize_phone(request.form["phone"])
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
        payment_type = request.form.get("payment_type", "renewal")
        selected_plan = config.plan.get(plan_name)
        if selected_plan is None:
            raise ValueError
        latest_payment = OwnerPayment.query.filter_by(owner_id=owner.id).order_by(
            OwnerPayment.payment_date.desc(), OwnerPayment.id.desc()
        ).first()
        # Preserve unused paid time when an owner renews before expiry.
        subscription_start_date = max(
            payment_date,
            owner.payment_due_date + timedelta(days=1),
        ) if owner.payment_due_date else payment_date
        if payment_type == "upgrade":
            current_plan = config.plan.get(owner.owner_plan)
            if (not current_plan or not owner.payment_due_date or owner.payment_due_date < payment_date
                    or int(selected_plan["member_allowed"]) <= int(current_plan["member_allowed"])):
                raise ValueError
            amount = plan_total(selected_plan) - plan_total(current_plan)
            if amount <= 0:
                raise ValueError
            subscription_start_date = (
                latest_payment.subscription_start_date or latest_payment.payment_date
            ) if latest_payment else payment_date
            remarks = "Subscription upgrade. " + (request.form.get("remarks", "").strip() or "")
        else:
            amount = plan_total(selected_plan)
            remarks = request.form.get("remarks", "").strip() or None
        owner.owner_plan = plan_name
        owner.payment_due_date = subscription_start_date + timedelta(days=int(selected_plan["days"]))
        owner.member_limit_warning_plan = None
        db.session.add(OwnerPayment(owner_id=owner.id, amount=amount, payment_date=payment_date,
                                    plan_name=plan_name, subscription_start_date=subscription_start_date,
                                    remarks=remarks))
        db.session.commit()
        flash("Subscription upgraded." if payment_type == "upgrade" else "Owner payment recorded.", "success")
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
        payment.amount = plan_total(config.plan[plan_name])
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
