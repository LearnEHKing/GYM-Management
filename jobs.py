from datetime import date, timedelta
import logging

from sqlalchemy import func, update
from models import Attendance, Member, GymOwner, db, local_today
import config
from send_message import send_whatsapp
from services.automatic_messages import (
    enqueue_automatic_message,
    send_queued_automatic_messages,
)

logger = logging.getLogger("gym_management.jobs")


def reconcile_active_member_counts():
    """Correct cached owner counters and warn when a mismatch is found."""
    rows = db.session.query(
        GymOwner.id,
        GymOwner.active_member_count,
        func.count(Member.id),
    ).outerjoin(
        Member,
        (Member.owner_id == GymOwner.id) & Member.membership_active.is_(True),
    ).group_by(GymOwner.id, GymOwner.active_member_count).all()
    mismatch_count = 0
    for owner_id, cached_count, actual_count in rows:
        if cached_count == actual_count:
            continue
        mismatch_count += 1
        logger.warning(
            "active member count mismatch corrected",
            extra={"context": {
                "owner_id": owner_id,
                "cached_count": cached_count,
                "actual_count": actual_count,
            }},
        )
        db.session.query(GymOwner).filter_by(id=owner_id).update(
            {GymOwner.active_member_count: actual_count},
            synchronize_session=False,
        )
    if mismatch_count:
        db.session.commit()
    logger.info(
        "active member count reconciliation complete",
        extra={"context": {"mismatches": mismatch_count}},
    )

def send_payment_reminders():
    """Queue today's member reminders, then deliver as many as quota permits."""
    logger.info("queueing membership reminders")
    target_dates = [
        local_today() + timedelta(days=int(days))
        for days in config.membership_reminder_days
    ]
    members = Member.query.filter(
        Member.membership_expiry.in_(target_dates),
        Member.membership_active.is_(True),
        Member.send_membership_reminder.is_(True),
        Member.owner.has(GymOwner.owner_plan.in_(
            [name for name, details in config.plan.items() if details.get("whatsapp_enabled")]
        )),
    ).all()
    logger.info("membership reminders selected", extra={"context": {"count": len(members)}})
    for member in members:
        days_left = (member.membership_expiry - local_today()).days
        message = config.reminder_message.format(
            member.name,
            member.owner.name,
            days_left,
            member.owner.phone,
            member.owner.name
        )
        enqueue_automatic_message(
            "membership_reminder", member.phone, message,
            f"membership_reminder:{member.id}:{member.membership_expiry.isoformat()}",
        )
    db.session.commit()
    sent = send_queued_automatic_messages(send_whatsapp)
    logger.info("membership reminders sent", extra={"context": {"count": sent}})

def send_owner_payment_reminders():
    """Queue today's owner reminders, then deliver as many as quota permits."""
    logger.info("queueing owner subscription reminders")

    owners = GymOwner.query.filter(
        GymOwner.payment_due_date.is_not(None),
        GymOwner.send_reminder.is_(True),
    ).all()
    for owner in owners:
        selected_plan = config.plan.get(owner.owner_plan)
        if not selected_plan:
            continue
        days_left = (owner.payment_due_date - local_today()).days
        if days_left not in {int(days) for days in config.owner_subscription_reminder_days}:
            continue
        message = config.owner_reminder_message.format(
            owner.name,
            days_left,
            owner.payment_due_date.strftime("%d %b %Y")
        )
        enqueue_automatic_message(
            "owner_payment_reminder", owner.phone, message,
            f"owner_payment_reminder:{owner.id}:{owner.payment_due_date.isoformat()}",
        )
    db.session.commit()
    sent = send_queued_automatic_messages(send_whatsapp)
    logger.info("owner subscription reminders sent", extra={"context": {"count": sent}})


def remove_inactive_members():
    """Mark members as removed after their owner's configured absence period."""
    today = local_today()
    last_attendance = db.session.query(
        Attendance.member_id,
        func.max(Attendance.attendance_date).label("last_attendance_date"),
    ).group_by(Attendance.member_id).subquery()
    candidate_members = db.session.query(
        Member, GymOwner.inactive_member_removal_days,
        last_attendance.c.last_attendance_date,
    ).outerjoin(
        last_attendance, last_attendance.c.member_id == Member.id
    ).join(GymOwner, GymOwner.id == Member.owner_id).filter(
        Member.membership_active.is_(True),
    ).all()
    inactive_members = [
        member for member, removal_days, last_attendance_date in candidate_members
        if (today - (last_attendance_date or member.join_date)).days >= max(int(removal_days or 30), 1)
    ]
    inactive_ids = [member.id for member in inactive_members]
    removed_count = len(inactive_ids)
    if inactive_ids:
        for member in inactive_members:
            if (member.owner.membership_removal_policy == "pause"
                    and member.membership_expiry):
                member.reserved_membership_days = max(
                    (member.membership_expiry - today).days + 1, 0
                )
            else:
                member.reserved_membership_days = 0
            member.membership_active = False
        for owner_id in {member.owner_id for member in inactive_members}:
            removed_for_owner = sum(member.owner_id == owner_id for member in inactive_members)
            db.session.execute(
                update(GymOwner).where(GymOwner.id == owner_id).values(
                    active_member_count=GymOwner.active_member_count - removed_for_owner
                )
            )

    if removed_count:
        db.session.commit()
    logger.info("inactive members removed", extra={"context": {"count": removed_count}})
