from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length

from app.auth.forms import strip


class DeviceForm(FlaskForm):
    name = StringField("Device name", filters=[strip], validators=[DataRequired(), Length(max=100)])
    submit = SubmitField("Add device")
