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


def recalculate_memberships(member):
    """Rebuild membership dates after a historic plan is edited or removed."""
    memberships = (Membership.query.filter_by(member_id=member.id)
                   .order_by(Membership.payment_date, Membership.id).all())
    previous_expiry = None
    for membership in memberships:
        membership.start_date = (previous_expiry + relativedelta(days=1)
                                 if previous_expiry and previous_expiry >= membership.payment_date
                                 else membership.payment_date)
        membership.expiry_date = (membership.start_date
                                  + relativedelta(months=membership.duration_months)
                                  - relativedelta(days=1))
        previous_expiry = membership.expiry_date

    if memberships:
        current = max(memberships, key=lambda item: (item.expiry_date, item.id))
        member.current_plan_id = current.plan_id
        member.membership_start = current.start_date
        member.membership_expiry = current.expiry_date
        member.active = current.expiry_date >= date.today()
    else:
        member.current_plan_id = None
        member.membership_start = None
        member.membership_expiry = None
        member.active = False
