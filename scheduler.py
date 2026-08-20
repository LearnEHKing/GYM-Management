# scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler

from backup import create_backup
from jobs import (
    send_payment_reminders,
    send_owner_payment_reminders,
    remove_inactive_members,
    
)

scheduler = BackgroundScheduler()
app = None


def init_scheduler(flask_app):
    """
    Initialize the scheduler and start all scheduled jobs.
    Call this once from main.py.
    """
    global app
    if scheduler.running:
        # Application factories can be called more than once (for example by
        # a test runner).  The existing jobs already use the active app.
        return
    app = flask_app
    # -----------------5-------
    # Daily database backup
    # Every day at 1:00 AM
    # -------------------------
    scheduler.add_job(
        func=backup_job,
        trigger="cron",
        hour=1,
        minute=00,
        id="daily_backup",
        replace_existing=True,
        misfire_grace_time=3000,  # 50 minutes
        coalesce=True,
        max_instances=1,
    )
    # -------------------------
    # send_payment_reminders
    # Every day at 8:00 AM
    # -------------------------
    scheduler.add_job(
        func=job_send_payment_reminders,
        trigger="cron",
        hour=8,
        minute=0,
        id="payment_reminders",
        replace_existing=True,
        misfire_grace_time=3000,  # 50 minutes
        coalesce=True,
        max_instances=1,
    )
    # -------------------------
    # send_owner_payment_reminders
    # Every day at 9:00 AM
    # -------------------------
    scheduler.add_job(
        func=job_send_owner_payment_reminders,
        trigger="cron",
        hour=9,
        minute=00,
        id="owner_payment_reminders",
        replace_existing=True,
        misfire_grace_time=3000,  # 50 minutes
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        func=job_remove_inactive_members,
        trigger="cron",
        hour=0,
        minute=30,
        id="inactive_member_removal",
        replace_existing=True,
        misfire_grace_time=3000,
        coalesce=True,
        max_instances=1,
    )

    scheduler.start()


def backup_job():
    """Runs the daily backup."""
    with app.app_context():
        print("[Scheduler] Running daily backup...")
        create_backup()

      
def job_send_payment_reminders():
    with app.app_context():
        send_payment_reminders()
      
def job_send_owner_payment_reminders():
    with app.app_context():
        send_owner_payment_reminders()


def job_remove_inactive_members():
    with app.app_context():
        remove_inactive_members()

def shutdown_scheduler():
    """Stops the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown()
