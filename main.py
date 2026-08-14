from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, login_user , login_required, logout_user
from werkzeug.security import generate_password_hash,check_password_hash
from models import GymOwner,db

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

  app.run()
  
