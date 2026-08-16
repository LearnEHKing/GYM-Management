from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, login_user , login_required, logout_user
from werkzeug.security import generate_password_hash,check_password_hash
from models import GymOwner, db, Member, Payment, OwnerPayment
import config 
from datetime import datetime, date

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
    return render_template("home.html",active_page="home")
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
  
      plan = request.form["plan"]
      payment_status = request.form["payment_status"]
  
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
  
      elif Member.query.filter_by(
              owner_id=current_user.id,
              phone=phone
          ).first():
  
          errors["phone"] = "This phone number already exists."
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
  
          fee = int(request.form["fee"])
  
          if fee <= 0:
              errors["fee"] = "Fee must be greater than 0."
  
      except ValueError:
  
          errors["fee"] = "Enter a valid fee."
  
      # -------------------------
      # Membership Plan
      # -------------------------
  
      valid_plans = {
          "Monthly",
          "2 Months",
          "3 Months",
          "4 Months",
          "5 Months",
          "6 Months",
          "Yearly"
      }
  
      if plan not in valid_plans:
          errors["plan"] = "Invalid membership plan."
  
      # -------------------------
      # Payment Status
      # -------------------------
  
      valid_status = {
          "Paid",
          "Pending",
          "Partial"
      }
  
      if payment_status not in valid_status:
          errors["payment_status"] = "Invalid payment status."
  
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
  
              payment = Payment(
                  member_id=member.id,
                  plan_name=plan,
                  amount=fee,
                  amount_paid=fee if payment_status == "Paid" else 0,
                  status=payment_status,
                  payment_date=join_date,
                  start_date=join_date,
                  expiry_date=join_date,
                  duration_days=6
              )
  
              db.session.add(payment)
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
    server_error=server_error
)
  

@app.route("/members/<int:member_id>/edit", methods=["GET", "POST"])
@login_required
def edit_member(member_id):
  member = Member.query.get_or_404(member_id)
  errors={}
  server_error=False
  if request.method == "POST":
  
      name = request.form["name"].strip()
      phone = request.form["phone"].strip()
      address = request.form["address"].strip()
      notes = request.form["notes"].strip()
  
      plan = request.form["plan"]
      payment_status = request.form["payment_status"]
  
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
  
      elif Member.query.filter_by(
              owner_id=current_user.id,
              phone=phone
          ).first():
  
          errors["phone"] = "This phone number already exists."
      if name!=member.name and Member.query.filter_by( owner_id=current_user.id, name=name).first():
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
  
          fee = int(request.form["fee"])
  
          if fee <= 0:
              errors["fee"] = "Fee must be greater than 0."
  
      except ValueError:
  
          errors["fee"] = "Enter a valid fee."
  
      # -------------------------
      # Membership Plan
      # -------------------------
  
      valid_plans = {
          "Monthly",
          "2 Months",
          "3 Months",
          "4 Months",
          "5 Months",
          "6 Months",
          "Yearly"
      }
  
      if plan not in valid_plans:
          errors["plan"] = "Invalid membership plan."
  
      # -------------------------
      # Payment Status
      # -------------------------
  
      valid_status = {
          "Paid",
          "Pending",
          "Partial"
      }
  
      if payment_status not in valid_status:
          errors["payment_status"] = "Invalid payment status."
  
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
  
              payment = Payment(
                  member_id=member.id,
                  plan_name=plan,
                  amount=fee,
                  amount_paid=fee if payment_status == "Paid" else 0,
                  status=payment_status,
                  payment_date=join_date,
                  start_date=join_date,
                  expiry_date=join_date,
                  duration_days=6
              )
  
              db.session.add(payment)
              db.session.commit()
  
              flash("Member edited successfully!", "success")
  
              return redirect(url_for(f"members/{member_id}"))
  
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
  

@app.route("/members/<int:member_id>")
@login_required
def member_details(member_id):
    member = Member.query.get_or_404(member_id)
    # Security check
    if member.owner_id != current_user.id:
        abort(403)  # Forbidden

    return render_template("member_details.html", member=member)
  

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
    plan = request.form.get("plan", "").strip()
    join_date = datetime.strptime(request.form["join_date"], "%Y-%m-%d").date()
    due_value = request.form.get("payment_due_date", "")
    due_date = datetime.strptime(due_value, "%Y-%m-%d").date() if due_value else None
    if not all((username, password, name, phone, plan)):
      raise ValueError("Username, password, gym name, phone, and plan are required.")
    if len(password) < 8:
      raise ValueError("Password must contain at least 8 characters.")
    if GymOwner.query.filter_by(username=username).first():
      raise ValueError("That username is already in use.")
    db.session.add(GymOwner(username=username, password_hash=generate_password_hash(password), name=name, phone=phone, join_date=join_date, payment_due_date=due_date, plan=plan))
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
    owner.plan = request.form["plan"].strip()
    owner.join_date = datetime.strptime(request.form["join_date"], "%Y-%m-%d").date()
    due_value = request.form.get("payment_due_date", "")
    owner.payment_due_date = datetime.strptime(due_value, "%Y-%m-%d").date() if due_value else None
    password = request.form.get("password", "")
    if password:
      if len(password) < 8:
        raise ValueError
      owner.password_hash = generate_password_hash(password)
    if not all((owner.name, owner.phone, owner.plan)):
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


if __name__=="__main__":
  with app.app_context():
    db.create_all()
  app.run()
  
