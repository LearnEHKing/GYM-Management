from werkzeug.security import generate_password_hash

admin = {
    "username":"admin",
    "password":generate_password_hash("ddd")}



