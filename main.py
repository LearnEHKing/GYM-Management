from flask_login import LoginManager, current_user, login_user , login_required, logout_user
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from models import GymOwner, db, Member, Payment, OwnerPayment, MembershipPlan
from werkzeug.security import generate_password_hash,check_password_hash
from dateutil.relativedelta import relativedelta
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from sqlalchemy import func
import config 

app = Flask(__name__)
app.secret_key = "ppp"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///gym.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
db.init_app(app)


@login_manager.user_loader
def load_user(user_id):
   return GymOwner.query.get(int(user_id))

@app.route("/")
def index():
  if current_user.is_authenticated:
    
    return render_template("home.html",active_page="home",total_members = Member.query.filter_by(owner_id=current_user.id).count() )
  return render_template("index.html")
  
@app.route("/add_member", methods=["GET", "POST"])
@login_required
def add_member():
  errors={}
  server_error=False
  if request.method == "POST":
  
      name = request.form["name"].strip()
      phone = request.form["phone"].strip()
      address = request.form["address"].strip()
      notes = request.form["notes"].strip()
      plan = MembershipPlan.query.get_or_404(request.form["plan_id"])
      amount_paid = int(request.form["fee"].strip())
      if amount_paid == 0:
          payment_status = "Pending"
      elif amount_paid < plan.fee:
          payment_status = "Partial"
      else:
          payment_status = "Paid"
  
      # -------------------------
      # Name
      # -------------------------
  
      if len(name) < 3:
          errors["name"] = "Name must contain at least 3 characters."
  
      elif len(name) > 100:
          errors["name"] = "Name is too long."
  
      # -------------------------
      # Phone
      # -------------------------
  
      if not phone.isdigit():
          errors["phone"] = "Phone number must contain only digits."
  
      elif len(phone) != 10:
          errors["phone"] = "Phone number must contain exactly 10 digits."
        
      if Member.query.filter_by( owner_id=current_user.id, name=name).first():
        errors["name"] = (
          "A member with this name already exists. "
          "Please add a surname or father's name.")
      # -------------------------
      # Address
      # -------------------------
  
      if len(address) < 3:
          errors["address"] = "Please enter a valid address."
  
      # -------------------------
      # Join Date
      # -------------------------
  
      try:
  
          join_date = datetime.strptime(
              request.form["join_date"],
              "%Y-%m-%d"
          ).date()
  
          if join_date > date.today():
              errors["join_date"] = "Joining date cannot be in the future."
  
      except ValueError:
          errors["join_date"] = "Invalid joining date."
  
      # -------------------------
      # Fee
      # -------------------------
  
      try:
          if amount_paid <= 0:
              errors["fee"] = "Paid Amount must be greater than 0."
          if amount_paid>plan.fee:
              errors["fee"] = f"Paid Amount cannot be greater than the membership plan - {plan.fee}."
            

        
      except ValueError:
  
          errors["fee"] = "Enter a valid fee."
  
      # -------------------------
      # Save
      # -------------------------
  
      if not errors:
          try:
      
              member = Member(
                  owner_id=current_user.id,
                  name=name,
                  phone=phone,
                  address=address,
                  join_date=join_date,
                  notes=notes
              )
      
              db.session.add(member)
              db.session.flush()
      
              new_payment(
                  member=member,
                  plan=plan,
                  amount_paid=amount_paid,
                  payment_date=join_date,
                  status=payment_status,
                  remarks=""
              )
      
              db.session.commit()
      
              flash("Member added successfully!", "success")
              return redirect(url_for("add_member"))
      
          except Exception as e:
      
              print(e)
              db.session.rollback()
              server_error = True
            
  return render_template(
    "add_member.html",
    errors=errors,
    server_error=server_error,
    plans = [plan for plan in current_user.plans if plan.active]
)
  

@app.route("/members/<int:member_id>/edit", methods=["GET", "POST"])
@login_required
def edit_member(member_id):

    member = Member.query.filter_by(
        id=member_id,
        owner_id=current_user.id
    ).first_or_404()

    errors = {}
    server_error = False

    if request.method == "POST":

        name = request.form["name"].strip()
        phone = request.form["phone"].strip()
        address = request.form["address"].strip()
        notes = request.form["notes"].strip()

        # -------------------------
        # Name
        # -------------------------

        if len(name) < 3:
            errors["name"] = "Name must contain at least 3 characters."

        elif len(name) > 100:
            errors["name"] = "Name is too long."

        # Duplicate name
        elif (
            name != member.name and
            Member.query.filter_by(
                owner_id=current_user.id,
                name=name
            ).first()
        ):
            errors["name"] = (
                "A member with this name already exists. "
                "Please add a surname or father's name."
            )

        # -------------------------
        # Phone
        # -------------------------

        if not phone.isdigit():
            errors["phone"] = "Phone number must contain only digits."

        elif len(phone) != 10:
            errors["phone"] = "Phone number must contain exactly 10 digits."

        # -------------------------
        # Address
        # -------------------------

        if len(address) < 3:
            errors["address"] = "Please enter a valid address."

        # -------------------------
        # Save
        # -------------------------

        if not errors:
            try:

                member.name = name
                member.phone = phone
                member.address = address
                member.notes = notes

                db.session.commit()

                flash("Member updated successfully!", "success")

                return redirect(url_for(
                    "members",
                    member_id=member.id
                ))

            except Exception as e:

                print(e)
                db.session.rollback()
                server_error = True

    return render_template(
        "edit_member.html",
        member=member,
        errors=errors,
        server_error=server_error
    )


@app.route("/attendance",methods=['GET','POST'])
@login_required
def attendance():
  return render_template("attendance.html")

@app.route("/manage_payment",methods=['GET','POST'])
@login_required
def manage_payment():
  return render_template("manage_payment.html")

@app.route("/stats",methods=['GET','POST'])
@login_required
def stats():
  return render_template("stats.html")

@app.route("/members",methods=['GET'])
@login_required
def members():
  members = current_user.members
  return render_template("members.html", members=members, active_page="members")

@app.route("/settings",methods=['GET'])
@login_required
def settings():
  return render_template("settings.html",active_page="settings")

@app.route("/settings/plans", methods=["POST"])
@login_required
def create_plan():

    name = request.form["name"].strip()
    months = int(request.form["duration_months"])
    fee = int(request.form["fee"])

    plan = MembershipPlan(
        owner_id=current_user.id,
        name=name,
        duration_months=months,
        fee=fee
    )

    db.session.add(plan)
    db.session.commit()

    return redirect(url_for("settings"))

@app.route("/members/<int:member_id>")
@login_required
def member_details(member_id):
    member = Member.query.get_or_404(member_id)
    # Security check
    if member.owner_id != current_user.id:
        abort(403)  # Forbidden

    total_paid = db.session.query(func.sum(Payment.amount_paid)).filter_by(member_id=member.id).scalar() or 0

    payment_count = Payment.query.filter_by(member_id=member.id).count()

    membership_months = (
      (date.today().year - member.join_date.year) * 12 +
      date.today().month - member.join_date.month
    )
    
    attendance_this_month = 21      # Calculate from Attendance table later
    last_visit = "Yesterday"        # Replace once attendance is implemented
    
    return render_template(
      "member_details.html",
      member=member,
      total_paid=total_paid,
      membership_months=membership_months,
      attendance_this_month=attendance_this_month,
      last_visit=last_visit,
      today=date.today(),
      payments = (
        Payment.query
        .filter_by(member_id=member.id)
        .order_by(Payment.payment_date.desc())
        .all()
      )
    )




@app.route("/payments/<int:member_id>", methods=["GET", "POST"])
@login_required
def new_payment(member_id):
    return f"Hehehe yr id is {member_id} "

@app.route("/payments/<int:payment_id>/edit", methods=["GET", "POST"])
@login_required
def edit_payment(payment_id):

    payment = (
        Payment.query
        .join(Member)
        .filter(
            Payment.id == payment_id,
            Member.gym_owner_id == current_user.id
        )
        .first_or_404()
    )

    if request.method == "POST":

        payment.plan_name = request.form["plan_name"]
        payment.amount_paid = int(request.form["amount_paid"])
        payment.status = request.form["status"]
        payment.remarks = request.form["remarks"]

        db.session.commit()

        return redirect(url_for(
            "member_details",
            member_id=payment.member_id
        ))

    return render_template(
        "edit_payment.html",
        payment=payment
    )
    

@app.route("/login",methods=['GET','POST'])
def login():
  if current_user.is_authenticated:
    return redirect("/")

  error=None
  if request.method == "POST":
      # POST request
    username = request.form["username"]
    password = request.form["password"]
    owner = GymOwner.query.filter_by(username=username).first()
    if owner and check_password_hash(owner.password_hash,password):
      login_user(owner)
      return redirect("/")
    else :
      error="Invalid username or password."
  return render_template("login.html",error=error)

@app.route('/logout')
@login_required
def logout():
  logout_user()
  return redirect("/")




#====================================
#            ADMIN 
#====================================

@app.route("/admin", methods=['GET','POST'])
@login_required
def admin():
    # /login has already verified the password.  This route only decides
    # whether the logged-in owner is the configured administrator.
    if current_user.username != config.admin["username"]:
        abort(403)
    if request.method == "POST":
        pass
    owners = GymOwner.query.order_by(GymOwner.join_date.desc()).all()
    owner_payments = OwnerPayment.query.order_by(OwnerPayment.payment_date.desc()).all()
    return render_template(
        "admin.html",
        active_page="admin",
        owners=owners,
        owner_payments=owner_payments,
        today=date.today(),
    )


    
@app.route("/admin/owners", methods=["POST"])
@login_required
def create_owner():
  if current_user.username != config.admin["username"]:
    abort(403)
  try:
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    plan_names = request.form.getlist("plan_name[]")
    plan_durations = request.form.getlist("plan_duration[]")
    plan_fees = request.form.getlist("plan_fee[]")
    join_date = datetime.strptime(request.form["join_date"], "%Y-%m-%d").date()
    due_value = request.form.get("payment_due_date", "")
    due_date = datetime.strptime(due_value, "%Y-%m-%d").date() if due_value else None
    if not all((username, password, name, phone, plan_names, plan_durations, plan_fees)):
      raise ValueError("Username, password, gym name, phone, and plan are required.")
    if len(password) < 8:
      raise ValueError("Password must contain at least 8 characters.")
    if GymOwner.query.filter_by(username=username).first():
      raise ValueError("That username is already in use.")
    owner = GymOwner(
        username=username,
        password_hash=generate_password_hash(password),
        name=name,
        phone=phone,
        join_date=join_date,
        payment_due_date=due_date,
    )
    
    db.session.add(owner)
    db.session.flush()      # Gives owner.id before commit
    
    for name, duration, fee in zip(plan_names, plan_durations, plan_fees):
        db.session.add(
            MembershipPlan(
                owner_id=owner.id,
                name=name,
                duration_months=int(duration),
                fee=int(fee)
            ))
    
    db.session.commit()
    flash(f"Created the {name} owner profile.", "success")
  except (KeyError, ValueError):
    db.session.rollback()
    flash("Enter all required owner details and a password of at least 8 characters.", "error")
  return redirect(url_for("admin"))


@app.route("/admin/owners/<int:owner_id>", methods=["POST"])
@login_required
def edit_owner(owner_id):
  if current_user.username != config.admin["username"]:
    abort(403)
  owner = GymOwner.query.get_or_404(owner_id)
  try:
    username = request.form.get("username", "").strip()
    duplicate = GymOwner.query.filter(GymOwner.username == username, GymOwner.id != owner.id).first()
    if not username or duplicate:
      raise ValueError
    owner.username = username
    owner.name = request.form["name"].strip()
    owner.phone = request.form["phone"].strip()
    
    owner.join_date = datetime.strptime(request.form["join_date"], "%Y-%m-%d").date()
    due_value = request.form.get("payment_due_date", "")
    owner.payment_due_date = datetime.strptime(due_value, "%Y-%m-%d").date() if due_value else None
    password = request.form.get("password", "")
    if password:
      if len(password) < 8:
        raise ValueError
      owner.password_hash = generate_password_hash(password)
    if not all((owner.name, owner.phone)):
      raise ValueError
    db.session.commit()
    flash(f"Updated {owner.name}.", "success")
  except (KeyError, ValueError):
    db.session.rollback()
    flash("Could not update the owner. Check all fields and ensure the username is unique.", "error")
  return redirect(url_for("admin"))


@app.route("/admin/owner-payments", methods=["POST"])
@login_required
def create_owner_payment():
  if current_user.username != config.admin["username"]:
    abort(403)
  try:
    owner = GymOwner.query.get_or_404(int(request.form["owner_id"]))
    amount = int(request.form["amount"])
    status = request.form.get("status", "Paid")
    if amount <= 0 or status not in {"Paid", "Partial", "Pending"}:
      raise ValueError
    payment_date = datetime.strptime(request.form["payment_date"], "%Y-%m-%d").date()
    db.session.add(OwnerPayment(owner_id=owner.id, amount=amount, status=status, payment_date=payment_date, remarks=request.form.get("remarks", "").strip() or None))
    db.session.commit()
    flash("Owner payment recorded.", "success")
  except (KeyError, TypeError, ValueError):
    db.session.rollback()
    flash("Enter valid owner payment details.", "error")
  return redirect(url_for("admin"))






def new_payment(
    member,
    plan,
    amount_paid,
    payment_date,
    status,
    remarks=""
):
    """
    Creates a payment and updates the member's current membership.
    Does NOT commit the database.
    """

    expiry_date = payment_date + relativedelta(
        months=plan.duration_months
    )

    payment = Payment(
        member_id=member.id,

        plan_id=plan.id,
        plan_name=plan.name,

        duration_months=plan.duration_months,

        fee=plan.fee,
        amount_paid=amount_paid,

        payment_date=payment_date,

        start_date=payment_date,
        expiry_date=expiry_date,

        status=status,
        remarks=remarks
    )

    db.session.add(payment)

    # Cache current membership on Member
    member.current_plan = plan.name
    member.membership_start = payment_date
    member.membership_expiry = expiry_date
    member.active = expiry_date >= date.today()

    return payment


if __name__=="__main__":
  with app.app_context():
    db.create_all()
  app.run()
  
