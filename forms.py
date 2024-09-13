from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, TextAreaField, SelectMultipleField, widgets
from wtforms.validators import DataRequired, EqualTo, Length, Email, URL
import email_validator


class MultiCheckboxField(SelectMultipleField):
    """
    A multiple-select, except displays a list of checkboxes.

    Iterating the field will produce subfields, allowing custom rendering of
    the enclosed checkbox fields.
    """
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class RecipeForm(FlaskForm):
    title = StringField("Recipe Name", validators=[DataRequired(), Length(max=100)])
    ingredients = TextAreaField("List of Ingredients (+Quantity/Units if desired)", validators=[DataRequired()])
    instructions = TextAreaField("Step-By-Step Instructions", validators=[DataRequired()])
    type_diet = MultiCheckboxField("Type of Diet", choices=[
        ('vegetarian', 'Vegetarian'), ('vegan', "Vegan"), ('gf', 'Gluten-free'), ('keto', 'Keto')])
    submit = SubmitField("Submit Recipe!")


class RegisterForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=50)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=100)])
    password = PasswordField(label="Password",
                             validators=[DataRequired(),
                                         Length(max=100),
                                         EqualTo("confirm_password", message="Passwords must match")])
    confirm_password = PasswordField("Confirm Password")
    submit = SubmitField("Submit")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log In")


# class CommentForm(FlaskForm):
#     body = CKEditorField("Comment", validators=[DataRequired()])
#     submit = SubmitField("Submit Comment")


class AIQueryForm(FlaskForm):
    query = StringField("ex. \"Korean recipe with garlic, onions, rice, and gochujang\"", validators=[DataRequired()])
    submit = SubmitField("Submit")
