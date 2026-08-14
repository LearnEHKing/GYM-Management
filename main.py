from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, login_user , login_required, logout_user
from werkzeug.security import generate_password_hash,check_password_hash
from models import GymOwner,db, Member, Payment
import config 
from datetime import datetime

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
    return render_template("home.html")
  return render_template("index.html")
  
@app.route("/add_member", methods=["GET", "POST"])
@login_required
def add_member():
    if request.method == "POST":
      try:
        
        
        # Member details
        name = request.form["name"]
        phone = request.form["phone"]
        address = request.form["address"]
        notes = request.form["notes"]
        join_date = datetime.strptime(
            request.form["join_date"], "%Y-%m-%d"
        ).date()

        # Payment details
        plan = request.form["plan"]
        fee = int(request.form["fee"])
        payment_status = request.form["payment_status"]

        # Create member
        member = Member(
            owner_id=current_user.id,
            name=name,
            phone=phone,
            address=address,
            join_date=join_date,
            notes=notes
        )

        db.session.add(member)
        db.session.flush()  # Gives member.id before commit

        # Create first payment
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
        return redirect("/")
      except Exception as e:
        print("\n\n", e , "\n\n")
    return render_template("add_member.html")

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

    
if __name__=="__main__":
  with app.app_context():
    db.create_all()
  app.run()
  
