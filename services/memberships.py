from datetime import date

from dateutil.relativedelta import relativedelta

from models import Membership, db


def new_membership(member, plan, amount_paid, payment_date, remarks=""):
    """Create a membership payment and update the member; do not commit."""
    start_date = (member.membership_expiry + relativedelta(days=1)
                  if member.membership_expiry and member.membership_expiry >= payment_date
                  else payment_date)
    expiry_date = start_date + relativedelta(months=plan.duration_months) - relativedelta(days=1)
    membership = Membership(member_id=member.id, plan_id=plan.id, plan_name=plan.name,
                            duration_months=plan.duration_months, fee=plan.fee,
                            amount_paid=amount_paid, payment_date=payment_date,
                            start_date=start_date, expiry_date=expiry_date, remarks=remarks)
    db.session.add(membership)
    member.current_plan_id = plan.id
    member.membership_start = start_date
    member.membership_expiry = expiry_date
    member.active = expiry_date >= date.today()
    return membership
