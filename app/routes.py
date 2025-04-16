from datetime import datetime, timezone

from flask import render_template, flash, redirect, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
import sqlalchemy as sa
from urllib.parse import urlsplit

from app import app
from app import db
from app.forms import EditProfileForm, EmptyForm, LoginForm, RegistrationForm
from app.models import User


@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        # We don't need to add user here because we know it's already in the db (else there wouldn't be a current user)
        db.session.commit()


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


@app.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash("Your changes have been saved.")
        return redirect(url_for("edit_profile"))
    elif request.method == "GET":
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template("edit_profile.html", title="Edit Profile", form=form)


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


# When a url component contains < >, the text portion is passed in as a parameter of the same name, in this case, username
@app.route("/user/<username>")
@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    posts = [
        {"author": user, "body": "Test post #1"},
        {"author": user, "body": "Test post #2"},
    ]
    form = EmptyForm()
    return render_template("user.html", user=user, posts=posts, form=form)


@app.route("/follow/<username>", methods=["POST"])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.username == username))
        if user is None:
            flash(f"User {username} not found.")
            return redirect(url_for("index"))
        if user == current_user:
            flash(
                "You're so vain. You can't follow yourself. Get your head out of your ass."
            )
            return redirect(url_for("user", username=username))
        current_user.follow(user)
        db.session.commit()
        flash(f"You are now following {username}!")
        return redirect(url_for("user", username=username))
    else:
        return redirect(url_for("index"))


@app.route("/unfollow/<username>", methods=["POST"])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.username == username))
        if user is None:
            flash(f"User {username} not found.")
            return redirect(url_for("index"))
        if user == current_user:
            flash("You can't unfollow yourself.")
            return redirect(url_for("user", username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(f"You are not following {username}.")
        return redirect(url_for("user", username=username))
    else:
        return redirect(url_for("index"))
