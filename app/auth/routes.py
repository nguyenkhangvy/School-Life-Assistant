from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user
from sqlalchemy import select

from app.auth.forms import LoginForm, RegisterForm
from app.auth.models import User
from app.extensions import db, login_manager

bp = Blueprint("auth", __name__, url_prefix="/auth")


def safe_next_url(target):
    """Return target only if it is a path on this site, so login can't forward to another site."""
    if not target or not target.startswith("/") or target.startswith(("//", "/\\")):
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return None
    return target


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(email=form.email.data, display_name=form.display_name.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("main.index"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(select(User).filter_by(email=form.email.data)).scalar_one_or_none()
        if user is not None and user.check_password(form.password.data):
            login_user(user)
            return redirect(safe_next_url(request.args.get("next")) or url_for("main.index"))
        flash("Email or password is incorrect.", "error")
    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
