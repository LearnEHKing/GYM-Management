from datetime import date, timedelta
from sqlalchemy import func

from models import db, Member, GymOwner, Attendance
import config

from send_message import send_whatsapp

def send_payment_reminders():
    print("Sending reminders...")
    target_dates = [
        date.today() + timedelta(days=int(days))
        for days in config.membership_reminder_days
    ]
    members = Member.query.filter(
        Member.membership_expiry.in_(target_dates),
        Member.send_membership_reminder == True,
        Member.owner.has(GymOwner.send_reminder == True)
    ).all()
    print("\n\nMembers length:{}\n\n".format(len(members)))
    for member in members:
        message = config.reminder_message.format(
            member.name,
            member.owner.name,
            member.membership_expiry-date.today(),
            member.owner.phone,
            member.owner.name
        )
        try :
            send_whatsapp(member.phone, message)
        except Exception as e:
            print("Failed to send message. ERROR : {}".format(e))
      
    db.session.commit()

def send_owner_payment_reminders():
    print("Sending owner subscription reminders...")

    reminder_days = (15, 7, 1)

    for days_left in reminder_days:
        target = date.today() + timedelta(days=days_left)

        owners = GymOwner.query.filter(
            GymOwner.payment_due_date == target
        ).all()

        for owner in owners:
            message = config.owner_reminder_message.format(
                owner.name,
                days_left,
                owner.payment_due_date.strftime("%d %b %Y")
            )
            try :
                send_whatsapp(owner.phone, message)
            except Exception as e:
                print("Failed to send message. ERROR : {}".format(e))