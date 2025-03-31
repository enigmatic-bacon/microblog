from flask import render_template, flash, redirect, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
import sqlalchemy as sa
from urllib.parse import urlsplit

from app import app
from app import db
from app.forms import LoginForm, RegistrationForm
from app.models import User


@app.route("/")
@app.route("/index")
@login_required
def index():
    user = {"username": "Alex"}
    posts = [
        {"author": {"username": "John"}, "body": "Beautiful day in Portland!"},
        {"author": {"username": "Susan"}, "body": "The avengers movie was so cool!"},
    ]
    return render_template("index.html", title="Home", posts=posts)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data)
        )
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password")
            return redirect(url_for("login"))
        login_user(user, remember=form.remember_me.data)
        # If a non-logged in-user tries to access /index, it'll add the query to url as such: /login?next=/index
        next_page = request.args.get("next")
        # netloc gets domain name of url (ex: example.com/path.netloc -> example.com)
        # this check avoid redirecting to external site which would be an avenue for a phishing attack (open redirect)
        if not next_page or urlsplit(next_page).netloc != "":
            next_page = url_for("index")
        return redirect(next_page)
    return render_template("login.html", title="Sign In", form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = RegistrationForm()
    # Was the form submitted (is this a post request), and did all the validators pass
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Good job, you signed up. Whoopie.")
        return redirect(url_for("login"))
    return render_template("register.html", title="Register", form=form)
