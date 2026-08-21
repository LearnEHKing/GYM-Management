import json
import os
from pathlib import Path


def required_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set in the environment.")
    return value


admin = {
    "username": required_env("ADMIN_USERNAME"),
}

membership_reminder_days = [7, 2, 0]

# Maximum number of automatic WhatsApp messages sent in a calendar day.  Set to
# 0 to hold all automatic messages until the limit is increased.  Messages over
# this limit remain queued and are tried again on the next day.
daily_message_limit = 249

# GYM-Manager subscriptions for gym owners. Edit this catalog to add or change
# the plans available when recording an owner payment.
plan = {
    "starter": {"days": 30, "whatsapp_reminder_days": [7, 2, 0], "member_allowed": 50, "fee": 499, "whatsapp_enabled": False, "whatsapp_fee": 0},
    "growth": {"days": 30, "whatsapp_reminder_days": [7, 2, 0], "member_allowed": 150, "fee": 999, "whatsapp_enabled": True, "whatsapp_fee": 199},
    "pro": {"days": 30, "whatsapp_reminder_days": [7, 2, 0], "member_allowed": 500, "fee": 1499, "whatsapp_enabled": True, "whatsapp_fee": 299},
}

# Send the capacity message once when a new member takes the count above this
# many places below the limit.
plan_delta_members_before_warning = 5

# Values changed from the administrator settings page are kept out of source
# control and loaded whenever the application starts.
_runtime_settings_path = Path(__file__).with_name("instance") / "admin_settings.json"


def _validate_runtime_settings(values):
    if not isinstance(values, dict):
        raise RuntimeError("instance/admin_settings.json must contain a JSON object.")
    expected_keys = {
        "membership_reminder_days",
        "daily_message_limit",
        "plan_delta_members_before_warning",
    }
    if set(values) != expected_keys:
        raise RuntimeError(
            "instance/admin_settings.json contains unknown or missing settings."
        )

    reminder_days = values["membership_reminder_days"]
    if (not isinstance(reminder_days, list) or not reminder_days
            or any(isinstance(day, bool) or not isinstance(day, int) or not 0 <= day <= 365
                   for day in reminder_days)
            or len(set(reminder_days)) != len(reminder_days)):
        raise RuntimeError("membership_reminder_days must be unique integers from 0 to 365.")

    for key in ("daily_message_limit", "plan_delta_members_before_warning"):
        value = values[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RuntimeError(f"{key} must be a non-negative integer.")
    return values


def _load_runtime_settings():
    try:
        values = json.loads(_runtime_settings_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except OSError as error:
        raise RuntimeError(f"Could not read {_runtime_settings_path}: {error}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Invalid JSON in {_runtime_settings_path}: {error}") from error
    return _validate_runtime_settings(values)


def update_runtime_settings(reminder_days, message_limit, warning_delta):
    """Persist validated administrator settings and apply them immediately."""
    values = _validate_runtime_settings({
        "membership_reminder_days": reminder_days,
        "daily_message_limit": message_limit,
        "plan_delta_members_before_warning": warning_delta,
    })
    _runtime_settings_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = _runtime_settings_path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(values, indent=2), encoding="utf-8")
    temporary_path.replace(_runtime_settings_path)
    globals().update(values)


_runtime_settings = _load_runtime_settings()
if _runtime_settings:
    membership_reminder_days = _runtime_settings["membership_reminder_days"]
    daily_message_limit = _runtime_settings["daily_message_limit"]
    plan_delta_members_before_warning = _runtime_settings["plan_delta_members_before_warning"]

member_limit_warning_message = (
    "👋 Hi {},\n\n"
    "⚠️ Your gym is getting close to its member limit. You can add up to "
    "*{} members* on your current {} plan, and you currently have *{}*.\n\n"
    "Please update your plan in order to keep adding more members.\n\n"
    "🤖 Sent automatically by GYM-Manager"
)

reminder_message = (
    "👋 Hi {},\n\n"
    "⏰ Just a friendly reminder that your membership at *{}💪* "
    "will expire in *{} days*.\n\n"
    "Renew your membership before it expires to continue your fitness journey without interruption.\n\n"
    "📞 Need any help? Feel free to contact us at {}.\n\n"
    "Thank you,\n"
    "*{}*\n\n"
    "- by GYM-Manager"
)

owner_reminder_message = (
    "👋 Hi {},\n\n"
    "⏰ This is a reminder that your GYM-Manager subscription "
    "will expire in *{} day(s)* "
    "(on *{}*).\n\n"
    "✅ Please renew your subscription before the due date to "
    "ensure uninterrupted access to your gym management system.\n\n"
    "🙏 Thank you for choosing GYM-Manager!\n\n"
    "🤖 Sent automatically by GYM-Manager"
)
