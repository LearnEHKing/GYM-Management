from flask_login import LoginManager, current_user, login_user , login_required, logout_user
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from models import GymOwner, db, Member, Membership, OwnerPayment, MembershipPlan
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
   return db.session.get(GymOwner, int(user_id))

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
              trial_start = join_date
              trial_expiry = join_date + relativedelta(days=current_user.trial_days)
              
              member.membership_start = trial_start
              member.membership_expiry = trial_expiry
              member.active = True
              
              db.session.add(
                  Membership(
                      member_id=member.id,
                      plan_id=None,
                      plan_name="Trial",
                      duration_months=0,
                      fee=0,
                      amount_paid=0,
                      payment_date=join_date,
                      start_date=trial_start,
                      expiry_date=trial_expiry,
                      remarks="Trial membership"
                  )
              )
              
      
              db.session.commit()
            
              flash("Member added successfully!", "success")
              return redirect(
                  url_for("member_details", member_id=member.id)
                            )
                          
          except Exception as e:
      
              print(e)
              db.session.rollback()
              server_error = True
            
  return render_template(
    "add_member.html",
    errors=errors,
    server_error=server_error
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
                    "member_details",
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
    try :
        name = request.form["name"].strip()
        months = int(request.form["duration_months"])
        fee = int(request.form["fee"])
        if not name:
            flash("Plan name is required.", "error")
            return redirect(url_for("settings"))
        if months<0 or fee<0:
            flash("Invalid data.", "error")
            return redirect(url_for("settings"))
        plan = MembershipPlan(
            owner_id=current_user.id,
            name=name,
            duration_months=months,
            fee=fee
        )
    
        db.session.add(plan)
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        flash("Server error! Please try again.", "error")
        return redirect(url_for("settings"))

    return redirect(url_for("settings"))

@app.route("/members/<int:member_id>")
@login_required
def member_details(member_id):
    member = Member.query.get_or_404(member_id)
    # Security check
    if member.owner_id != current_user.id:
        abort(403)  # Forbidden

    total_paid = db.session.query(func.sum(Membership.amount_paid)).filter_by(member_id=member.id).scalar() or 0

    payment_count = Membership.query.filter_by(member_id=member.id).count()

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
        Membership.query
        .filter_by(member_id=member.id)
        .order_by(Membership.payment_date.desc())
        .all()
      )
    )




@app.route("/members/<int:member_id>/membership", methods=["GET", "POST"])
@login_required
def add_membership(member_id):

    member = Member.query.get_or_404(member_id)
    plans = MembershipPlan.query.filter_by(
        owner_id=current_user.id,
        active=True
    ).all()
    if member.owner_id != current_user.id:
      abort(403)

    errors = {}

    if request.method == "POST":

        # -------------------------
        # Read form
        # -------------------------

        plan_id = request.form.get("plan_id")
        amount_paid = request.form.get("amount_paid")
        payment_date = request.form.get("payment_date")
        remarks = request.form.get("remarks", "").strip()

        # -------------------------
        # Validation
        # -------------------------

        plan = MembershipPlan.query.filter_by(
            id=plan_id,
            owner_id=current_user.id,
            active=True
        ).first()

        if not plan:
            errors["plan_id"] = "Please select a membership plan."

        try:
            amount_paid = int(amount_paid)

            if amount_paid <= 0 or amount_paid>plan.fee:
                raise ValueError

        except (TypeError, ValueError):
            errors["amount_paid"] = "Enter a valid amount."

        try:
            payment_date = datetime.strptime(
                payment_date,
                "%Y-%m-%d"
            ).date()

        except (TypeError, ValueError):
            errors["payment_date"] = "Invalid payment date."

        # -------------------------
        # Save
        # -------------------------

        if not errors:

            try:

                new_membership(
                    member=member,
                    plan=plan,
                    amount_paid=amount_paid,
                    payment_date=payment_date,
                    remarks=remarks
                )

                db.session.commit()

                flash("Payment recorded successfully.", "success")

                return redirect(
                    f"/members/{member.id}"
                )

            except Exception:

                db.session.rollback()

                return render_template(
                    "payment.html",
                    member=member,
                    plans=plans,
                    errors=errors,
                    server_error=True
                )

    return render_template(
        "payment.html",
        member=member,
        plans=plans,
        errors=errors,
        server_error=False
    )

@app.route("/membership/<int:membership_id>/delete", methods=["POST"])
@login_required
def delete_membership(membership_id):

    membership = (
        Membership.query
        .join(Member)
        .filter(
            Membership.id == membership_id,
            Member.owner_id == current_user.id
        )
        .first_or_404()
    )

    member = membership.member

    try:
        db.session.delete(membership)
        db.session.flush()

        latest = (
            Membership.query
            .filter_by(member_id=member.id)
            .order_by(Membership.expiry_date.desc())
            .first()
        )

        if latest:
            member.current_plan_id = latest.plan_id
            member.membership_start = latest.start_date
            member.membership_expiry = latest.expiry_date
            member.active = latest.expiry_date >= date.today()
        else:
            member.current_plan_id = None
            member.membership_start = None
            member.membership_expiry = None
            member.active = False

        db.session.commit()
        flash("Membership deleted successfully.", "success")

    except Exception as e:
        print(e)
        db.session.rollback()
        flash("Could not delete membership.", "error")

    return redirect(url_for(
        "member_details",
        member_id=member.id
    ))

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
    
    for plan_name, duration, fee in zip(plan_names, plan_durations, plan_fees):
        db.session.add(
            MembershipPlan(
                owner_id=owner.id,
                name=plan_name,
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
    payment_date = datetime.strptime(request.form["payment_date"], "%Y-%m-%d").date()
    db.session.add(OwnerPayment(owner_id=owner.id, amount=amount, payment_date=payment_date, remarks=request.form.get("remarks", "").strip() or None))
    db.session.commit()
    flash("Owner payment recorded.", "success")
  except (KeyError, TypeError, ValueError):
    db.session.rollback()
    flash("Enter valid owner payment details.", "error")
  return redirect(url_for("admin"))





  
def new_membership(  
    member,  
    plan,  
    amount_paid,  
    payment_date,  
    remarks=""  
):  
    """  
    Creates a payment and updates the member's current membership.  
    Does NOT commit the database.  
    """  
  
    
    if member.membership_expiry and member.membership_expiry >= payment_date:
        start_date = member.membership_expiry + relativedelta(days=1)
    else:
        start_date = payment_date

    expiry_date = (
      start_date +
      relativedelta(months=plan.duration_months) -
      relativedelta(days=1)
    )
    membership = Membership(  
        member_id=member.id,  
  
        plan_id=plan.id,  
        plan_name=plan.name,  
  
        duration_months=plan.duration_months,  
  
        fee=plan.fee,  
        amount_paid=amount_paid,  
  
        payment_date=payment_date,  
  
        start_date=start_date,  
        expiry_date=expiry_date,  
        remarks=remarks  
    )  
  
    db.session.add(membership)  
  
    # Cache current membership on Member  
    member.current_plan_id = plan.id
    member.membership_start = start_date  
    member.membership_expiry = expiry_date  
    member.active = expiry_date >= date.today()  
  
    return membership



if __name__=="__main__":
  with app.app_context():
    db.create_all()
  app.run()
  
