from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import EmailField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from app.auth.models import User
from app.extensions import db


def normalize_email(value):
    return value.strip().lower() if value else value


def strip(value):
    return value.strip() if value else value


class RegisterForm(FlaskForm):
    email = EmailField(
        "Email", filters=[normalize_email], validators=[DataRequired(), Email(), Length(max=255)]
    )
    display_name = StringField(
        "Display name", filters=[strip], validators=[DataRequired(), Length(max=100)]
    )
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords don't match.")],
    )
    submit = SubmitField("Create account")

    def validate_email(self, field):
        if db.session.execute(select(User.id).filter_by(email=field.data)).first():
            raise ValidationError("This email is already registered.")


class LoginForm(FlaskForm):
    email = EmailField("Email", filters=[normalize_email], validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")
