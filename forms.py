from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SubmitField, PasswordField, TextAreaField, SelectMultipleField, widgets, IntegerField
from wtforms.validators import DataRequired, EqualTo, Length, Email, Optional, URL, NumberRange
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
    title = StringField("Recipe Name", [DataRequired(), Length(max=100)])
    description = StringField("Description", [Length(max=400)])
    ingredients = TextAreaField("List of Ingredients (+Quantity/Units if desired)", [DataRequired()])
    instructions = TextAreaField("Step-By-Step Instructions", [DataRequired()])
    servings = IntegerField("Number of Servings", [DataRequired(), NumberRange(min=1, max=10)])
    time_hours = IntegerField("Hours", [Optional(), NumberRange(min=0, max=48)])
    time_mins = IntegerField("Minutes", [Optional(), NumberRange(min=1, max=60)])
    type_diet = MultiCheckboxField("Type of Diet", choices=[
        ('vegetarian', 'Vegetarian'), ('vegan', "Vegan"), ('gf', 'Gluten-free'), ('keto', 'Keto'), ('lc', 'Low-carb')])
    image_upload = FileField("Image Upload", [FileAllowed(["jpg", "jpeg", "png"], "Images only")])
    image_url = StringField("OR Provide an Image URL", [Optional(), URL()])
    submit = SubmitField("Submit Recipe!")


class RegisterForm(FlaskForm):
    name = StringField("Username", [DataRequired(), Length(max=50)])
    email = StringField("Email", [DataRequired(), Email(allow_empty_local=True), Length(max=100)])
    password = PasswordField("Password", [DataRequired(), Length(max=100)])
    confirm_password = PasswordField("Confirm Password",
                                     [EqualTo("password", "Passwords must match")])
    submit = SubmitField("Submit")


class RegisterCont(FlaskForm):
    description = StringField("Tell us about yourself!", [Length(max=200)])
    image_upload = FileField("Profile Picture", [FileAllowed(["jpg", "jpeg", "png"], "Images only")])
    submit = SubmitField("Submit")


class EditProfileForm(FlaskForm):
    name = StringField("New username?", [Length(max=50)])
    description = StringField(validators=[Length(max=200)])
    image_upload = FileField("New profile picture?", [FileAllowed(["jpg", "jpeg", "png"], "Images only")])
    email = StringField("New email?", [Optional(), Email(), Length(max=100)])
    password = PasswordField("New password?", [Length(max=100)])
    confirm_password = PasswordField("Confirm Password",
                                     [EqualTo("password", "Passwords must match")])
    submit = SubmitField("Submit")


class LoginForm(FlaskForm):
    email = StringField("Email", [DataRequired()])
    password = PasswordField("Password", [DataRequired()])
    submit = SubmitField("Log In")


class CommentForm(FlaskForm):
    body = TextAreaField("", validators=[DataRequired()], render_kw={"id": "comment-box"})
    submit = SubmitField("Submit Comment")


class AIQueryForm(FlaskForm):
    query = StringField("ex. \"Korean recipe with garlic, onions, rice, and gochujang\"", [DataRequired()])
    submit = SubmitField("Submit")


class GetRecipeForm(FlaskForm):
    recipe_url = StringField("Recipe URL",
                             [DataRequired(), URL()],
                             # render_kw={"placeholder": "Recipe URL"}
                             )
    submit = SubmitField("Submit")
