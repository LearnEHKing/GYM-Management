from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user
from sqlalchemy import func

from models import Attendance, EditHistory, GymOwner, Member, Membership, MembershipPlan, db, local_now, local_today
from services.memberships import new_membership, recalculate_memberships
from services.edit_history import record_edit
from services.automatic_messages import enqueue_automatic_message
from observability import report_unexpected_error
from services.phone import normalize_phone
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

import config

members_bp = Blueprint("members", __name__)


def validate_member_form(member=None):
    name = request.form["name"].strip()
    try:
        phone = normalize_phone(request.form["phone"])
    except ValueError:
        phone = request.form.get("phone", "").strip()
    address = request.form["address"].strip()
    # HTML form values are strings, and unchecked checkboxes are omitted entirely.
    send_membership_reminder = (
        current_user.whatsapp_enabled
        and request.form.get("send_membership_reminder") == "True"
    )
    notes = request.form["notes"].strip()
    errors = {}
    if len(name) < 3:
        errors["name"] = "Name must contain at least 3 characters."
    elif len(name) > 100:
        errors["name"] = "Name is too long."
    elif Member.query.filter_by(owner_id=current_user.id, name=name).first() not in (None, member):
        errors["name"] = "A member with this name already exists. Please add a surname or father's name."
    if not phone.startswith("+91") or len(phone) != 13:
        errors["phone"] = "Enter a valid Indian mobile number."
    if len(address) < 3:
        errors["address"] = "Please enter a valid address."
    return name, phone, send_membership_reminder, address, notes, errors


def get_owned_member(member_id):
    return Member.query.filter_by(id=member_id, owner_id=current_user.id).first_or_404()


def membership_snapshot(membership):
    return {
        "plan_id": membership.plan_id,
        "plan_name": membership.plan_name,
        "duration_months": membership.duration_months,
        "fee": membership.fee,
        "amount_paid": membership.amount_paid,
        "payment_date": membership.payment_date.isoformat(),
        "start_date": membership.start_date.isoformat(),
        "expiry_date": membership.expiry_date.isoformat(),
        "remarks": membership.remarks,
    }


@members_bp.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.username == config.admin["username"]:
            return redirect("/admin")
        elif current_user.payment_due_date and local_today() > current_user.payment_due_date:
            logout_user()
            return redirect(url_for("members.plan_over"))

        today = local_today()
        month_start = today.replace(day=1)
        # Removed members do not use a seat on the gym owner's subscription.
        # An expired membership is still a member and remains counted.
        total_members = Member.query.filter_by(
            owner_id=current_user.id, membership_active=True
        ).count()
        monthly_revenue = db.session.query(func.sum(Membership.amount_paid)).join(Member).filter(
            Member.owner_id == current_user.id,
            Membership.payment_date >= month_start,
            Membership.payment_date <= today,
        ).scalar() or 0
        today_attendance = Attendance.query.join(Member).filter(
            Member.owner_id == current_user.id,
            Member.membership_active.is_(True),
            Attendance.attendance_date == today,
        ).count()
        expired_members = Member.query.filter(
            Member.owner_id == current_user.id,
            Member.membership_active.is_(True),
            Member.membership_expiry < today,
        ).order_by(Member.membership_expiry.asc(), Member.name.asc()).all()
        expiring_soon = Member.query.filter(
            Member.owner_id == current_user.id,
            Member.membership_active.is_(True),
            Member.membership_expiry >= today,
            Member.membership_expiry <= today + relativedelta(days=7),
        ).order_by(Member.membership_expiry.asc(), Member.name.asc()).all()

        return render_template(
            "home.html", active_page="home", total_members=total_members,
            monthly_revenue=monthly_revenue, today_attendance=today_attendance,
            expiring_soon=len(expiring_soon), expired_members=expired_members,
            expiring_members=expiring_soon, today=today,
        )
    return render_template("index.html")

@members_bp.route("/plan_over")
def plan_over():
    return render_template("plan_over.html")

@members_bp.route("/add_member", methods=["GET", "POST"])
@login_required
def add_member():
    errors, server_error = {}, False
    if request.method == "POST":
        name, phone, send_membership_reminder, address, notes, errors = validate_member_form()
        try:
            join_date = datetime.strptime(request.form["join_date"], "%Y-%m-%d").date()
            if join_date > local_today():
                errors["join_date"] = "Joining date cannot be in the future."
        except ValueError:
            errors["join_date"] = "Invalid joining date."
        if not errors:
            owner_plan = config.plan.get(current_user.owner_plan)
            if owner_plan is None:
                errors["plan"] = "Your gym does not have an active GYM-Manager plan. Please contact the administrator."
            else:
                # A removed member frees a subscription seat; an expired member
                # remains part of the gym until they are explicitly removed.
                member_count = Member.query.filter_by(
                    owner_id=current_user.id, membership_active=True
                ).count()
                if member_count >= int(owner_plan["member_allowed"]):
                    errors["plan"] = "You have reached your plan's member limit. Please update your plan to add more members."
        if not errors:
            try:
                trial_days = int(current_user.trial_days)
                capacity_update = db.session.query(GymOwner).filter(
                    GymOwner.id == current_user.id,
                    GymOwner.active_member_count < int(owner_plan["member_allowed"]),
                ).update(
                    {GymOwner.active_member_count: GymOwner.active_member_count + 1},
                    synchronize_session=False,
                )
                if capacity_update != 1:
                    db.session.rollback()
                    errors["plan"] = "You have reached your plan's member limit. Please update your plan to add more members."
                    return render_template("add_member.html", errors=errors, server_error=server_error)
                member = Member(owner_id=current_user.id, name=name, phone=phone, send_membership_reminder=send_membership_reminder,address=address, join_date=join_date, notes=notes)
                db.session.add(member)
                db.session.flush()
                if trial_days > 0:
                    member.membership_start = join_date
                    member.membership_expiry = join_date + relativedelta(days=trial_days - 1)
                    member.membership_active = True
                    db.session.add(Membership(
                        member_id=member.id, plan_id=None, plan_name="Trial",
                        duration_months=0, fee=0, amount_paid=0,
                        payment_date=join_date, start_date=member.membership_start,
                        expiry_date=member.membership_expiry, remarks="Trial membership",
                    ))
                else:
                    member.membership_start = join_date
                    member.membership_expiry = join_date - timedelta(days=1)
                member.membership_active = True
                new_member_count = member_count + 1
                warning_threshold = int(owner_plan["member_allowed"]) - int(config.plan_delta_members_before_warning)
                should_send_limit_warning = (new_member_count > warning_threshold and current_user.member_limit_warning_plan != current_user.owner_plan)
                if should_send_limit_warning:
                    current_user.member_limit_warning_plan = current_user.owner_plan
                    enqueue_automatic_message(
                        "member_limit_warning",
                        current_user.phone,
                        config.member_limit_warning_message.format(
                            current_user.name, owner_plan["member_allowed"],
                            current_user.owner_plan.title(), new_member_count,
                        ),
                        f"member_limit_warning:{current_user.id}:{current_user.owner_plan}",
                    )
                db.session.commit()
                flash("Member added successfully!", "success")
                return redirect(url_for("members.member_details", member_id=member.id))
            except IntegrityError:
                db.session.rollback()
                errors["name"] = "A member with this name already exists."
            except SQLAlchemyError as error:
                db.session.rollback()
                report_unexpected_error(error, "members.add_member")
                server_error = True
    return render_template("add_member.html", errors=errors, server_error=server_error)


@members_bp.route("/members/<int:member_id>/edit", methods=["GET", "POST"])
@login_required
def edit_member(member_id):
    member = Member.query.filter_by(id=member_id, owner_id=current_user.id).first_or_404()
    errors, server_error = {}, False
    if request.method == "POST":
        name, phone, send_membership_reminder, address, notes, errors = validate_member_form(member)
        if not errors:
            try:
                member.name, member.phone, member.send_membership_reminder, member.address, member.notes = name, phone, send_membership_reminder, address, notes
                db.session.commit()
                flash("Member updated successfully!", "success")
                return redirect(url_for("members.member_details", member_id=member.id))
            except Exception as error:
                print(error)
                db.session.rollback()
                server_error = True
    return render_template("edit_member.html", member=member, errors=errors, server_error=server_error)


@members_bp.route("/attendance")
@login_required
def attendance():
    """Show today's check-in board, prioritised by yesterday's arrival time."""
    today = local_today()
    yesterday = today - relativedelta(days=1)
    now = local_now()

    members = Member.query.filter_by(owner_id=current_user.id).all()
    # Attendance remains available after expiry. Only explicitly removed
    # members are excluded from member actions.
    attendance_enabled_ids = {member.id for member in members if member.membership_active}
    today_attendance = {
        record.member_id: record
        for record in Attendance.query.join(Member).filter(
            Member.owner_id == current_user.id,
            Attendance.attendance_date == today,
        ).all()
    }
    yesterday_attendance = {
        record.member_id: record
        for record in Attendance.query.join(Member).filter(
            Member.owner_id == current_user.id,
            Attendance.attendance_date == yesterday,
        ).all()
    }

    def member_order(member):
        # Active members who still need a check-in are always first.  Within that
        # group, yesterday's matching hour is first, then the neighbouring hours.
        attendance_record = today_attendance.get(member.id)
        if member.id not in attendance_enabled_ids:
            status_rank = 2
        elif attendance_record is None:
            status_rank = 0
        else:
            status_rank = 1

        yesterday_record = yesterday_attendance.get(member.id)
        if yesterday_record:
            hour_distance = abs(yesterday_record.check_in.hour - now.hour)
            yesterday_rank = 0
        else:
            hour_distance = 99
            yesterday_rank = 1
        return status_rank, yesterday_rank, hour_distance, member.name.lower()

    ordered_members = sorted(members, key=member_order)
    return render_template(
        "attendance.html",
        members=ordered_members,
        attendance_by_member=today_attendance,
        today=today,
        attendance_enabled_ids=attendance_enabled_ids,
        active_unchecked=sum(m.id in attendance_enabled_ids and m.id not in today_attendance for m in members),
        active_page="attendance",
    )


@members_bp.route("/attendance/<int:member_id>/check-in", methods=["POST"])
@login_required
def check_in_member(member_id):
    member = Member.query.filter_by(id=member_id, owner_id=current_user.id).first_or_404()
    if member.membership_active:
        today = local_today()
        existing = Attendance.query.filter_by(member_id=member.id, attendance_date=today).first()
        if existing:
            flash(f"{member.name} is already checked in today.", "info")
        else:
            try:
                db.session.add(Attendance(member_id=member.id, attendance_date=today, check_in=local_now()))
                db.session.commit()
                flash(f"Attendance marked for {member.name}.", "success")
            except IntegrityError:
                db.session.rollback()
                flash(f"{member.name} is already checked in today.", "info")
    else:
        flash("Attendance is unavailable for a removed member.", "error")
    return redirect(url_for("members.attendance"))


@members_bp.route("/attendance/<int:member_id>/check-in/remove", methods=["POST"])
@login_required
def remove_check_in(member_id):
    member = Member.query.filter_by(id=member_id, owner_id=current_user.id).first_or_404()
    if member.membership_active:
        record = Attendance.query.filter_by(member_id=member.id, attendance_date=local_today()).first()
        if not record:
            flash(f"{member.name} has no attendance record for today.", "info")
        else:
            db.session.delete(record)
            db.session.commit()
            flash(f"Attendance removed for {member.name}.", "success")
    else:
        flash(f"Can't mark attencance for removed member.", "error")
    return redirect(url_for("members.attendance"))


@members_bp.route("/members/<int:member_id>/attendance", methods=["POST"])
@login_required
def edit_member_attendance(member_id):
    """Mark or remove one valid attendance date from a member profile."""
    member = Member.query.filter_by(id=member_id, owner_id=current_user.id).first_or_404()
    if member.membership_active:
        action = request.form.get("action")
        try:
            attendance_date = datetime.strptime(request.form.get("attendance_date", ""), "%Y-%m-%d").date()
        except ValueError:
            flash("Please choose a valid attendance date.", "error")
            return redirect(url_for("members.member_details", member_id=member.id))
    
        # Never accept future check-ins or dates from before the member existed.
        if attendance_date < member.join_date or attendance_date > local_today():
            flash("Attendance can only be edited between the joining date and today.", "error")
            return redirect(url_for("members.member_details", member_id=member.id))
    
        record = Attendance.query.filter_by(member_id=member.id, attendance_date=attendance_date).first()
        if action == "mark":
            if record:
                flash("Attendance is already marked for that date.", "info")
            else:
                check_in = datetime.combine(attendance_date, local_now().time())
                try:
                    db.session.add(Attendance(member_id=member.id, attendance_date=attendance_date, check_in=check_in))
                    db.session.commit()
                    flash("Attendance marked successfully.", "success")
                except IntegrityError:
                    db.session.rollback()
                    flash("Attendance is already marked for that date.", "info")
        elif action == "remove":
            if record:
                db.session.delete(record)
                db.session.commit()
                flash("Attendance removed successfully.", "success")
            else:
                flash("There is no attendance record for that date.", "info")
        else:
            abort(400)
    else:
        flash(f"Can't mark attencance for removed member.", "error")
    return redirect(url_for("members.member_details", member_id=member.id))


@members_bp.route("/reports")
@login_required
def reports():
    today = local_today()
    try:
        selected_days = int(request.args.get("days", 30))
    except (TypeError, ValueError):
        selected_days = 30
    if selected_days not in (7, 30, 90, 180):
        selected_days = 30
    report_start = today - relativedelta(days=selected_days - 1)
    attendance_rows = db.session.query(
        Attendance.attendance_date, func.count(Attendance.id)
    ).join(Member).filter(
        Member.owner_id == current_user.id,
        Attendance.attendance_date >= report_start,
        Attendance.attendance_date <= today,
    ).group_by(Attendance.attendance_date).all()
    attendance_counts = {record_date: count for record_date, count in attendance_rows}
    attendance_labels = []
    attendance_values = []
    for offset in range(selected_days - 1, -1, -1):
        day = today - relativedelta(days=offset)
        attendance_labels.append(day.strftime("%d %b"))
        attendance_values.append(attendance_counts.get(day, 0))

    revenue_rows = db.session.query(
        Membership.payment_date, func.sum(Membership.amount_paid)
    ).join(Member).filter(
        Member.owner_id == current_user.id,
        Membership.payment_date >= report_start,
        Membership.payment_date <= today,
    ).group_by(Membership.payment_date).all()
    revenue_counts = {record_date: int(amount) for record_date, amount in revenue_rows}
    revenue_values = [revenue_counts.get(today - relativedelta(days=offset), 0) for offset in range(selected_days - 1, -1, -1)]

    # Average visitors by hour
    hour_expression = func.extract("hour", Attendance.check_in)
    hour_rows = db.session.query(
        hour_expression,
        func.count(Attendance.id)
    ).join(Member).filter(
        Member.owner_id == current_user.id,
        Attendance.attendance_date >= report_start,
        Attendance.attendance_date <= today,
    ).group_by(
        hour_expression
    ).all()

    hour_counts = {int(hour): count for hour, count in hour_rows}

    busy_labels = [
        datetime.strptime(str(hour), "%H").strftime("%I %p")
        for hour in range(24)
    ]

    busy_values = [
        round(hour_counts.get(hour, 0) / selected_days, 1)
        for hour in range(24)
    ]

    peak_hour = max(hour_counts, key=hour_counts.get, default=0)
    busy_total = hour_counts.get(peak_hour, 0)
    busy_average = round(busy_total / selected_days, 1)
    busy_time = (
        f"{peak_hour:02d}:00 - {(peak_hour + 1) % 24:02d}:00"
    )


  
    total_attendance = sum(attendance_values)
    active_members = Member.query.filter_by(owner_id=current_user.id, membership_active=True).count()
    new_members = Member.query.filter(
        Member.owner_id == current_user.id,
        Member.join_date >= report_start,
        Member.join_date <= today,
    ).count()
    expiring_soon = Member.query.filter(
        Member.owner_id == current_user.id,
        Member.membership_active.is_(True),
        Member.membership_expiry >= today,
        Member.membership_expiry <= today + relativedelta(days=7),
    ).count()
    top_attendees = db.session.query(
        Member.name, func.count(Attendance.id).label("visits")
    ).join(Attendance).filter(
        Member.owner_id == current_user.id,
        Attendance.attendance_date >= report_start,
        Attendance.attendance_date <= today,
    ).group_by(Member.id, Member.name).order_by(func.count(Attendance.id).desc(), Member.name).limit(5).all()
    peak_index = max(range(len(attendance_values)), key=attendance_values.__getitem__)

    return render_template(
        "reports.html", active_page="reports",
        selected_days=selected_days, report_start=report_start, today=today,
        attendance_labels=attendance_labels, attendance_values=attendance_values,
        revenue_values=revenue_values, total_revenue=sum(revenue_values),
        active_members=active_members, new_members=new_members, expiring_soon=expiring_soon,
        total_attendance=total_attendance,
        average_attendance=round(total_attendance / selected_days, 1),
        peak_day=attendance_labels[peak_index], peak_count=attendance_values[peak_index],
        top_attendees=top_attendees,
        today_attendance=attendance_values[-1],
        busy_labels=busy_labels,
        busy_values=busy_values,
        busy_time=busy_time,
        busy_total=busy_total,
        busy_average=busy_average,
    )


@members_bp.route("/members")
@login_required
def members():
    members = Member.query.filter_by(owner_id=current_user.id).order_by(
        Member.membership_active.desc(),
        Member.name
    ).all()
    return render_template("members.html", members=members, active_page="members")


@members_bp.route("/members/<int:member_id>")
@login_required
def member_details(member_id):
    member = get_owned_member(member_id)
    total_paid = db.session.query(func.sum(Membership.amount_paid)).filter_by(member_id=member.id).scalar() or 0
    today = local_today()
    membership_months = (today.year - member.join_date.year) * 12 + today.month - member.join_date.month
    payments = Membership.query.filter_by(member_id=member.id).order_by(Membership.payment_date.desc()).all()
    current_membership = max(payments, key=lambda item: (item.expiry_date, item.id), default=None)
    payment_history = EditHistory.query.filter_by(
        owner_id=current_user.id, entity_type="membership", context_id=member.id
    ).order_by(
        EditHistory.created_at.desc(), EditHistory.id.desc()
    ).all()
    history_by_payment = {}
    for entry in payment_history:
        history_by_payment.setdefault(entry.entity_id, []).append(entry)
    deleted_payment_history = [entry for entry in payment_history if entry.action == "deleted"]
    plans = MembershipPlan.query.filter_by(owner_id=current_user.id, active=True).order_by(MembershipPlan.name).all()
    month_start = today.replace(day=1)
    attendance_this_month = Attendance.query.filter(
        Attendance.member_id == member.id,
        Attendance.attendance_date >= month_start,
        Attendance.attendance_date <= today,
    ).count()
    attendance_records = Attendance.query.filter_by(member_id=member.id).with_entities(
        Attendance.attendance_date, Attendance.check_in
    ).all()
    attendance_times = {
        record_date.isoformat(): check_in.strftime("%I:%M %p")
        for record_date, check_in in attendance_records
    }
    latest_attendance = Attendance.query.filter_by(member_id=member.id).order_by(
        Attendance.attendance_date.desc(), Attendance.check_in.desc()
    ).first()
    if latest_attendance:
        if latest_attendance.attendance_date == today:
            last_visit = "Today"
        elif latest_attendance.attendance_date == today - relativedelta(days=1):
            last_visit = "Yesterday"
        else:
            last_visit = latest_attendance.attendance_date.strftime("%d %b %Y")
    else:
        last_visit = "No visits yet"
    return render_template(
        "member_details.html", member=member, total_paid=total_paid,
        membership_months=membership_months, attendance_this_month=attendance_this_month,
        attendance_dates=list(attendance_times), attendance_times=attendance_times,
        last_visit=last_visit, today=today, payments=payments, plans=plans,
        current_membership=current_membership,
        history_by_payment=history_by_payment,
        deleted_payment_history=deleted_payment_history,
    )


@members_bp.route("/members/<int:member_id>/account_active-status", methods=["POST"])
@login_required
def toggle_membership_active_status(member_id):
    member = Member.query.filter_by(id=member_id, owner_id=current_user.id).first_or_404()
    try:
        updated = db.session.query(Member).filter_by(
            id=member.id, owner_id=current_user.id, membership_active=True
        ).update(
            {Member.membership_active: False}, synchronize_session=False
        )
        if updated == 1:
            if current_user.membership_removal_policy == "pause" and member.membership_expiry:
                member.reserved_membership_days = max((member.membership_expiry - local_today()).days + 1, 0)
            else:
                member.reserved_membership_days = 0
            db.session.query(GymOwner).filter_by(id=current_user.id).update(
                {GymOwner.active_member_count: GymOwner.active_member_count - 1},
                synchronize_session=False,
            )
            status = "removed"
        else:
            db.session.rollback()
            owner_plan = config.plan.get(current_user.owner_plan)
            if owner_plan is None:
                flash("Your gym does not have an active plan.", "error")
                return redirect(url_for("members.member_details", member_id=member.id))
            capacity_update = db.session.query(GymOwner).filter(
                GymOwner.id == current_user.id,
                GymOwner.active_member_count < int(owner_plan["member_allowed"]),
            ).update(
                {GymOwner.active_member_count: GymOwner.active_member_count + 1},
                synchronize_session=False,
            )
            if capacity_update != 1:
                flash("You have reached your plan's member limit.", "error")
                return redirect(url_for("members.member_details", member_id=member.id))
            updated = db.session.query(Member).filter_by(
                id=member.id, owner_id=current_user.id, membership_active=False
            ).update(
                {Member.membership_active: True}, synchronize_session=False
            )
            if updated != 1:
                db.session.rollback()
                flash("Member status was already changed.", "info")
                return redirect(url_for("members.member_details", member_id=member.id))
            if (current_user.membership_removal_policy == "pause"
                    and member.reserved_membership_days > 0):
                member.membership_start = local_today()
                member.membership_expiry = local_today() + relativedelta(
                    days=member.reserved_membership_days - 1
                )
                member.reserved_membership_days = 0
            status = "rejoined"
        db.session.commit()
        flash(f"{member.name} has been {status}.", "success")
    except Exception as error:
        print(error)
        db.session.rollback()
        flash("Could not update the account membership status.", "error")
    return redirect(url_for("members.member_details", member_id=member.id))


@members_bp.route("/members/<int:member_id>/delete", methods=["POST"])
@login_required
def permanently_delete_member(member_id):
    member = Member.query.filter_by(id=member_id, owner_id=current_user.id).first_or_404()
    member_name = member.name
    try:
        # The model relationships cascade to attendance and membership history.
        if member.membership_active:
            db.session.query(GymOwner).filter_by(id=current_user.id).update(
                {GymOwner.active_member_count: GymOwner.active_member_count - 1},
                synchronize_session=False,
            )
        db.session.delete(member)
        db.session.commit()
        flash(f"{member_name} and all of their information were permanently deleted.", "success")
    except Exception as error:
        print(error)
        db.session.rollback()
        flash("Could not permanently delete this member.", "error")
    return redirect(url_for("members.members"))


@members_bp.route("/membership/<int:membership_id>", methods=["POST"])
@login_required
def edit_membership(membership_id):
    membership = Membership.query.join(Member).filter(Membership.id == membership_id, Member.owner_id == current_user.id).first_or_404()
    member = membership.member
    try:
        reason = request.form.get("edit_reason", "").strip()
        if not 3 <= len(reason) <= 500:
            raise ValueError("reason")
        before_data = membership_snapshot(membership)
        plan_id = request.form.get("plan_id")
        if plan_id:
            try:
                plan_id = int(plan_id)
            except (TypeError, ValueError):
                raise ValueError
            plan = MembershipPlan.query.filter_by(id=plan_id, owner_id=current_user.id, active=True).first()
            if not plan:
                raise ValueError
            membership.plan_id = plan.id
            membership.plan_name = plan.name
            membership.duration_months = plan.duration_months
            membership.fee = plan.fee
            membership.amount_paid = plan.fee
        membership.remarks = request.form.get("remarks", "").strip()
        recalculate_memberships(member)
        record_edit(member.owner_id, current_user.id, current_user.username, "membership", membership.id, "updated", reason,
                before_data, membership_snapshot(membership), context_id=member.id)
        db.session.commit()
        flash("Payment history updated successfully.", "success")
    except ValueError:
        db.session.rollback()
        flash("Choose a valid membership plan and provide an edit reason (3 to 500 characters).", "error")
    except Exception as error:
        print(error)
        db.session.rollback()
        flash("Could not update the payment history.", "error")
    return redirect(url_for("members.member_details", member_id=member.id))


@members_bp.route("/members/<int:member_id>/membership", methods=["GET", "POST"])
@login_required
def add_membership(member_id):
    member = get_owned_member(member_id)
    plans = MembershipPlan.query.filter_by(owner_id=current_user.id, active=True).all()
    errors = {}
    if request.method == "POST":
        try:
            plan_id = int(request.form.get("plan_id", ""))
        except (TypeError, ValueError):
            plan_id = None
        plan = MembershipPlan.query.filter_by(id=plan_id, owner_id=current_user.id, active=True).first() if plan_id else None
        if not plan:
            errors["plan_id"] = "Please select a membership plan."
        try:
            payment_date = datetime.strptime(request.form.get("payment_date"), "%Y-%m-%d").date()
            if payment_date < member.join_date or payment_date > local_today():
                errors["payment_date"] = "Payment date must be between the joining date and today."
        except (TypeError, ValueError):
            errors["payment_date"] = "Invalid payment date."
        if not errors:
            try:
                # Take the fee from the server-side plan, never from the form.
                new_membership(member, plan, plan.fee, payment_date, request.form.get("remarks", "").strip())
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
        reason = request.form.get("edit_reason", "").strip()
        if not 3 <= len(reason) <= 500:
            raise ValueError
        before_data = membership_snapshot(membership)
        db.session.delete(membership)
        db.session.flush()
        recalculate_memberships(member)
        record_edit(member.owner_id, current_user.id, current_user.username, "membership", membership.id, "deleted", reason,
                before_data, None, context_id=member.id)
        db.session.commit()
        flash("Membership deleted successfully.", "success")
    except ValueError:
        db.session.rollback()
        flash("A deletion reason of 3 to 500 characters is required.", "error")
    except Exception as error:
        print(error)
        db.session.rollback()
        flash("Could not delete membership.", "error")
    return redirect(url_for("members.member_details", member_id=member.id))
