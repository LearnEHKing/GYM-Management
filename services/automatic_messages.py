"""Durable, quota-aware delivery for automatic WhatsApp messages."""

from datetime import date, datetime, time, timedelta

import config
from models import AutomaticMessage, db, local_now, local_today


def enqueue_automatic_message(kind, phone, message, dedupe_key):
    """Add a message to the outbox unless the same event is already queued."""
    existing = AutomaticMessage.query.filter_by(dedupe_key=dedupe_key).first()
    if existing:
        return existing, False

    queued_message = AutomaticMessage(
        kind=kind,
        phone=phone,
        message=message,
        dedupe_key=dedupe_key,
    )
    db.session.add(queued_message)
    return queued_message, True


def _daily_limit():
    try:
        return max(0, int(config.daily_message_limit))
    except (TypeError, ValueError):
        raise ValueError("config.daily_message_limit must be a non-negative integer")


def send_queued_automatic_messages(send_message, today=None):
    """Send pending messages up to today's quota and retain the rest for later."""
    limit = _daily_limit()
    if limit == 0:
        return 0

    today = today or local_today()
    day_start = datetime.combine(today, time.min)
    next_day = day_start + timedelta(days=1)
    already_sent = AutomaticMessage.query.filter(
        AutomaticMessage.sent_at >= day_start,
        AutomaticMessage.sent_at < next_day,
    ).count()
    available = max(0, limit - already_sent)
    if available == 0:
        return 0

    pending = AutomaticMessage.query.filter(
        AutomaticMessage.sent_at.is_(None)
    ).order_by(AutomaticMessage.created_at, AutomaticMessage.id).limit(available).all()

    sent = 0
    for queued_message in pending:
        try:
            send_message(queued_message.phone, queued_message.message)
        except Exception as error:
            queued_message.retry_count += 1
            queued_message.last_error = str(error)
            # Keep failures pending so a transient WhatsApp problem is retried.
            db.session.commit()
            continue

        queued_message.sent_at = local_now()
        queued_message.last_error = None
        db.session.commit()
        sent += 1
    return sent
