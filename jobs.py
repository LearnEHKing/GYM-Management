from datetime import date, timedelta
from sqlalchemy import func

from models import db, Member, GymOwner, Attendance
import config

from send_message import send_whatsapp

def send_payment_reminders():
    print("Sending reminders...")
    target = date.today() + timedelta(days=int(config.admin["membership_reminder_timedelta"]))

    members = Member.query.filter(
        Member.membership_expiry == target,
        Member.reminder_sent == False
    ).all()
    print("\n\nMembers length:{}\n\n".format(len(members)))
    for member in members:
        message = config.reminder_message.format(
            member.name,
            member.owner.name,
            config.admin["membership_reminder_timedelta"],
            member.owner.phone,
            member.owner.name
        )
        try :
            send_whatsapp(member.phone, message)
            member.reminder_sent = True
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