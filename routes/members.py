from datetime import date, datetime

from dateutil.relativedelta import relativedelta
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from models import Member, Membership, MembershipPlan, db
from services.memberships import new_membership

members_bp = Blueprint("members", __name__)


def validate_member_form(member=None):
    name = request.form["name"].strip()
    phone = request.form["phone"].strip()
    address = request.form["address"].strip()
    notes = request.form["notes"].strip()
    errors = {}
    if len(name) < 3:
        errors["name"] = "Name must contain at least 3 characters."
    elif len(name) > 100:
        errors["name"] = "Name is too long."
    elif Member.query.filter_by(owner_id=current_user.id, name=name).first() not in (None, member):
        errors["name"] = "A member with this name already exists. Please add a surname or father's name."
    if not phone.isdigit():
        errors["phone"] = "Phone number must contain only digits."
    elif len(phone) != 10:
        errors["phone"] = "Phone number must contain exactly 10 digits."
    if len(address) < 3:
        errors["address"] = "Please enter a valid address."
    return name, phone, address, notes, errors


@members_bp.route("/")
def index():
    if current_user.is_authenticated:
        total_members = Member.query.filter_by(owner_id=current_user.id).count()
        return render_template("home.html", active_page="home", total_members=total_members)
    return render_template("index.html")


@members_bp.route("/add_member", methods=["GET", "POST"])
@login_required
def add_member():
    errors, server_error = {}, False
    if request.method == "POST":
        name, phone, address, notes, errors = validate_member_form()
        try:
            join_date = datetime.strptime(request.form["join_date"], "%Y-%m-%d").date()
            if join_date > date.today():
                errors["join_date"] = "Joining date cannot be in the future."
        except ValueError:
            errors["join_date"] = "Invalid joining date."
        if not errors:
            try:
                member = Member(owner_id=current_user.id, name=name, phone=phone, address=address, join_date=join_date, notes=notes)
                db.session.add(member)
                db.session.flush()
                member.membership_start = join_date
                member.membership_expiry = join_date + relativedelta(days=current_user.trial_days)
                member.active = True
                db.session.add(Membership(member_id=member.id, plan_id=None, plan_name="Trial", duration_months=0, fee=0, amount_paid=0, payment_date=join_date, start_date=member.membership_start, expiry_date=member.membership_expiry, remarks="Trial membership"))
                db.session.commit()
                flash("Member added successfully!", "success")
                return redirect(url_for("members.member_details", member_id=member.id))
            except Exception as error:
                print(error)
                db.session.rollback()
                server_error = True
    return render_template("add_member.html", errors=errors, server_error=server_error)


@members_bp.route("/members/<int:member_id>/edit", methods=["GET", "POST"])
@login_required
def edit_member(member_id):
    member = Member.query.filter_by(id=member_id, owner_id=current_user.id).first_or_404()
    errors, server_error = {}, False
    if request.method == "POST":
        name, phone, address, notes, errors = validate_member_form(member)
        if not errors:
            try:
                member.name, member.phone, member.address, member.notes = name, phone, address, notes
                db.session.commit()
                flash("Member updated successfully!", "success")
                return redirect(url_for("members.member_details", member_id=member.id))
            except Exception as error:
                print(error)
                db.session.rollback()
                server_error = True
    return render_template("edit_member.html", member=member, errors=errors, server_error=server_error)


@members_bp.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():
    return render_template("attendance.html")


@members_bp.route("/manage_payment", methods=["GET", "POST"])
@login_required
def manage_payment():
    return render_template("manage_payment.html")


@members_bp.route("/stats", methods=["GET", "POST"])
@login_required
def stats():
    return render_template("stats.html")


@members_bp.route("/members")
@login_required
def members():
    return render_template("members.html", members=current_user.members, active_page="members")


@members_bp.route("/members/<int:member_id>")
@login_required
def member_details(member_id):
    member = Member.query.get_or_404(member_id)
    if member.owner_id != current_user.id:
        abort(403)
    total_paid = db.session.query(func.sum(Membership.amount_paid)).filter_by(member_id=member.id).scalar() or 0
    membership_months = (date.today().year - member.join_date.year) * 12 + date.today().month - member.join_date.month
    payments = Membership.query.filter_by(member_id=member.id).order_by(Membership.payment_date.desc()).all()
    return render_template("member_details.html", member=member, total_paid=total_paid, membership_months=membership_months, attendance_this_month=21, last_visit="Yesterday", today=date.today(), payments=payments)


@members_bp.route("/members/<int:member_id>/membership", methods=["GET", "POST"])
@login_required
def add_membership(member_id):
    member = Member.query.get_or_404(member_id)
    if member.owner_id != current_user.id:
        abort(403)
    plans = MembershipPlan.query.filter_by(owner_id=current_user.id, active=True).all()
    errors = {}
    if request.method == "POST":
        plan = MembershipPlan.query.filter_by(id=request.form.get("plan_id"), owner_id=current_user.id, active=True).first()
        if not plan:
            errors["plan_id"] = "Please select a membership plan."
        try:
            amount_paid = int(request.form.get("amount_paid"))
            if not plan or amount_paid <= 0 or amount_paid > plan.fee:
                raise ValueError
        except (TypeError, ValueError):
            errors["amount_paid"] = "Enter a valid amount."
        try:
            payment_date = datetime.strptime(request.form.get("payment_date"), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            errors["payment_date"] = "Invalid payment date."
        if not errors:
            try:
                new_membership(member, plan, amount_paid, payment_date, request.form.get("remarks", "").strip())
                db.session.commit()
                flash("Payment recorded successfully.", "success")
                return redirect(url_for("members.member_details", member_id=member.id))
            except Exception:
                db.session.rollback()
                return render_template("payment.html", member=member, plans=plans, errors=errors, server_error=True)
    return render_template("payment.html", member=member, plans=plans, errors=errors, server_error=False)


@members_bp.route("/membership/<int:membership_id>/delete", methods=["POST"])
@login_required
def delete_membership(membership_id):
    membership = Membership.query.join(Member).filter(Membership.id == membership_id, Member.owner_id == current_user.id).first_or_404()
    member = membership.member
    try:
        db.session.delete(membership)
        db.session.flush()
        latest = Membership.query.filter_by(member_id=member.id).order_by(Membership.expiry_date.desc()).first()
        if latest:
            member.current_plan_id, member.membership_start, member.membership_expiry = latest.plan_id, latest.start_date, latest.expiry_date
            member.active = latest.expiry_date >= date.today()
        else:
            member.current_plan_id = member.membership_start = member.membership_expiry = None
            member.active = False
        db.session.commit()
        flash("Membership deleted successfully.", "success")
    except Exception as error:
        print(error)
        db.session.rollback()
        flash("Could not delete membership.", "error")
    return redirect(url_for("members.member_details", member_id=member.id))
