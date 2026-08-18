# scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler

from backup import create_backup
from jobs import (
    mark_inactive_members,
    send_payment_reminders,
    send_owner_payment_reminders,
    
)

scheduler = BackgroundScheduler()
app = None


def init_scheduler(flask_app):
    """
    Initialize the scheduler and start all scheduled jobs.
    Call this once from main.py.
    """
    global app
    app = flask_app
    job_hr=9
    job_min=42
    # -------------------------
    # Daily database backup
    # Every day at 2:00 AM
    # -------------------------
    scheduler.add_job(
        func=backup_job,
        trigger="cron",
        hour=job_hr,
        minute=job_min,
        id="daily_backup",
        replace_existing=True,
    )

    # -------------------------
    # Mark inactive members
    # Every day at 3:00 AM
    # -------------------------
    scheduler.add_job(
        func=inactive_job,
        trigger="cron",
        hour=job_hr,
        minute=job_min,
        id="inactive_members",
        replace_existing=True,
    )
    # -------------------------
    # send_payment_reminders
    # Every day at 3:00 AM
    # -------------------------
    scheduler.add_job(
        func=job_send_payment_reminders,
        trigger="cron",
        hour=job_hr,
        minute=job_min,
        id="payment_reminders",
        replace_existing=True,
    )
    # -------------------------
    # send_owner_payment_reminders
    # Every day at 3:00 AM
    # -------------------------
    scheduler.add_job(
        func=job_send_owner_payment_reminders,
        trigger="cron",
        hour=job_hr,
        minute=job_min,
        id="owner_payment_reminders",
        replace_existing=True,
    )

    scheduler.start()


def backup_job():
    """Runs the daily backup."""
    with app.app_context():
        print("[Scheduler] Running daily backup...")
        create_backup()


def inactive_job():
    with app.app_context():
        mark_inactive_members()
      
def job_send_payment_reminders():
    with app.app_context():
        send_payment_reminders()
      
def job_send_owner_payment_reminders():
    with app.app_context():
        send_owner_payment_reminders()

def shutdown_scheduler():
    """Stops the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown()