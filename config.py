admin = {
    "username":"admin",
}
app_secret_key= "pe82uebdiw8wu"

membership_reminder_days = [7, 2, 0]

# Maximum number of automatic WhatsApp messages sent in a calendar day.  Set to
# 0 to hold all automatic messages until the limit is increased.  Messages over
# this limit remain queued and are tried again on the next day.
daily_message_limit = 249

# GYM-Manager subscriptions for gym owners. Edit this catalog to add or change
# the plans available when recording an owner payment.
plan = {
    "starter": {"days": 30, "whatsapp_reminder_days": [7, 2, 0], "member_allowed": 50, "fee": 499},
    "growth": {"days": 30, "whatsapp_reminder_days": [7, 2, 0], "member_allowed": 150, "fee": 999},
    "pro": {"days": 30, "whatsapp_reminder_days": [7, 2, 0], "member_allowed": 500, "fee": 1499},
}

# Send the capacity message once when a new member takes the count above this
# many places below the limit.
plan_delta_members_before_warning = 5

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
