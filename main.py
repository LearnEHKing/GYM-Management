from flask import Flask, render_template, redirect, url_for, request
#from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

app = Flask(__name__)
app.secret_key = "ppp"

#app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///gym.db"
#app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
#db = SQLAlchemy(app)

@app.route("/")
def index():
  return render_template("index.html")
  
@app.route("/login",methods=['GET','POST'])
def login():
  if request.method == "GET":
      return render_template("login.html")

    # POST request
  username = request.form["username"]
  password = request.form["password"]

    # Check database here
  if username == "admin" and password == "1234":
      session["user_id"] = 1
      return redirect("/")
  return render_template("login.html", error="Invalid username or password")

    

if __name__=="__main__":
  app.run()