from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    # A super-admin may be signed in while testing the customer journey in the
    # same browser. Sign that session out first; never turn a customer signup
    # into an admin session or send a customer to the admin dashboard.
    if current_user.is_authenticated:
        if current_user.is_admin:
            logout_user()
        else:
            return redirect(url_for("account"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 10:
            flash("Enter your name, email and a password of at least 10 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with this email already exists. Please sign in.", "error")
        else:
            user = User(name=name, email=email, password_hash=generate_password_hash(password), is_admin=False)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("account"))
    return render_template("auth.html", mode="Create account")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            logout_user()
        else:
            return redirect(url_for("account"))
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
        if user and check_password_hash(user.password_hash, request.form.get("password", "")):
            if user.is_admin:
                flash("This is an administrator account. Please use the private admin sign-in page.", "error")
                return redirect(url_for("admin.login"))
            login_user(user)
            target = request.args.get("next")
            if target and target.startswith("/") and not target.startswith("//") and not target.startswith("/admin"):
                return redirect(target)
            return redirect(url_for("account"))
        flash("Email or password is incorrect.", "error")
    return render_template("auth.html", mode="Sign in")

@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))
