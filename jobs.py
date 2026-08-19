from datetime import date, timedelta
from models import Member, GymOwner, db
import config
from send_message import send_whatsapp
from services.automatic_messages import (
    enqueue_automatic_message,
    send_queued_automatic_messages,
)

def send_payment_reminders():
    """Queue today's member reminders, then deliver as many as quota permits."""
    print("Queueing membership reminders...")
    target_dates = [
        date.today() + timedelta(days=int(days))
        for days in config.membership_reminder_days
    ]
    members = Member.query.filter(
        Member.membership_expiry.in_(target_dates),
        Member.membership_active.is_(True),
        Member.send_membership_reminder == True,
        Member.owner.has(GymOwner.send_reminder == True)
    ).all()
    print("\n\nMembers length:{}\n\n".format(len(members)))
    for member in members:
        days_left = (member.membership_expiry - date.today()).days
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
    print(f"Sent {sent} automatic WhatsApp message(s).")

def send_owner_payment_reminders():
    """Queue today's owner reminders, then deliver as many as quota permits."""
    print("Queueing owner subscription reminders...")

    owners = GymOwner.query.filter(GymOwner.payment_due_date.is_not(None)).all()
    for owner in owners:
        selected_plan = config.plan.get(owner.owner_plan)
        if not selected_plan:
            continue
        days_left = (owner.payment_due_date - date.today()).days
        if days_left not in {int(days) for days in selected_plan["whatsapp_reminder_days"]}:
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
    print(f"Sent {sent} automatic WhatsApp message(s).")
