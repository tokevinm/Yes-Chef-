import os
from typing import List
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from werkzeug.security import generate_password_hash, check_password_hash
from forms import RecipeForm, RegisterForm, LoginForm, AIQueryForm
from titlecase import titlecase
from groq import Groq
from markdown import markdown

API_KEY = "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"

client = Groq(
    api_key=API_KEY,
)

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6DonzWlSihBXox7C0sKR6d'

bootstrap = Bootstrap5(app)

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


@app.template_filter('titlecase')
def titlecase_filter(text):
    return titlecase(text)


class Base(DeclarativeBase):
    pass


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///recipes.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(50))
    recipes: Mapped[List["Recipe"]] = relationship(back_populates="author")
    # comments: Mapped[List["Comment"]] = relationship(back_populates="author")


class Recipe(db.Model):
    __tablename__ = "recipes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    ingredients: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    type_diet: Mapped[str] = mapped_column()
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    author: Mapped["User"] = relationship(back_populates="recipes")
    # comments: Mapped[List["Comment"]] = relationship(back_populates="parent_post", cascade="all, delete-orphan")


# class Comment(db.Model):
#     __tablename__ = "comments"
#     id: Mapped[int] = mapped_column(Integer, primary_key=True)
#     text: Mapped[str] = mapped_column(Text, nullable=False)
#     author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
#     author: Mapped["User"] = relationship(back_populates="comments")
#     post_id: Mapped[int] = mapped_column(Integer, ForeignKey("recipes.id"))
#     parent_post: Mapped["Recipe"] = relationship(back_populates="comments")


# class Image(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     filename = db.Column(db.String(255), nullable=False)


with app.app_context():
    db.create_all()


@app.route("/")
def home():
    result = db.session.execute(db.select(Recipe))
    recipes = result.scalars().all()[::-1]
    return render_template("index.html", recipes=recipes)


@app.route("/add-recipe", methods=['GET', 'POST'])
def add_recipe():
    form = RecipeForm(
        ingredients="<ul><li></li></ul>",
        instructions="<ol><li></li></ol>"
    )
    if form.validate_on_submit():
        title_input = form.title.data
        title_result = db.session.execute(db.select(Recipe).where(Recipe.title == title_input)).scalar()
        if title_result:
            flash("Recipe Name already exists :( Try something spicier, like \"Kevin's Hot and Sexy Chicken!\"")
            form = RecipeForm(
                title=form.title.data,
                ingredients=form.ingredients.data,
                instructions=form.instructions.data,
                type_diet=form.type_diet.data
            )
            return render_template("add-recipe.html", form=form)
        diets_string = ", ".join(form.type_diet.data)
        new_recipe = Recipe(
            title=form.title.data,
            ingredients=form.ingredients.data,
            instructions=form.instructions.data,
            type_diet=diets_string,
            author=current_user
        )
        db.session.add(new_recipe)
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("add-recipe.html", form=form)


@app.route("/recipe/<int:recipe_id>")
def display_recipe(recipe_id):
    requested_recipe = db.get_or_404(Recipe, recipe_id)
    return render_template(
        "recipe.html",
        recipe=requested_recipe,
        current_user=current_user,
    )


@app.route("/edit-recipe/<int:recipe_id>", methods=["GET", "POST"])
def edit_recipe(recipe_id):
    recipe = db.get_or_404(Recipe, recipe_id)
    edit_form = RecipeForm(
        title=recipe.title,
        ingredients=recipe.ingredients,
        instructions=recipe.instructions,
        type_diet=recipe.type_diet.split(", "),
        author=recipe.author,
    )
    if edit_form.validate_on_submit():
        diets_string = ", ".join(edit_form.type_diet.data)
        recipe.title = edit_form.title.data
        recipe.ingredients = edit_form.ingredients.data
        recipe.instructions = edit_form.instructions.data
        recipe.type_diet = diets_string
        recipe.author = current_user
        db.session.commit()
        return redirect(url_for("display_recipe", recipe_id=recipe.id))
    return render_template(
        "add-recipe.html",
        form=edit_form,
        is_edit=True,
        current_user=current_user
    )


@app.route("/delete/<int:recipe_id>")
def delete_recipe(recipe_id):
    recipe_to_delete = db.get_or_404(Recipe, recipe_id)
    db.session.delete(recipe_to_delete)
    db.session.commit()
    return redirect(url_for("home"))


# TODO Search function sucks, make better (Has to be exactly matching query, can't separate ingredients
#  by comma, or search phrases that don't exactly match)
@app.route("/search")
def search_recipe():
    search_param = request.args.get('query')
    title_results = Recipe.query.filter(Recipe.title.like(f'%{search_param}%')).all()
    ingredients_results = Recipe.query.filter(Recipe.ingredients.like(f'%{search_param}%')).all()
    instructions_results = Recipe.query.filter(Recipe.instructions.like(f'%{search_param}%')).all()
    recipes_set = set(title_results + ingredients_results + instructions_results)
    return render_template("index.html", recipes=recipes_set)


@app.route("/ai-recipe", methods=["GET", "POST"])
def ai_recipe():
    form = AIQueryForm()
    if form.validate_on_submit():
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a chef with knowledge in every culture and cuisine. Use only "
                               "user provided and common household ingredients to respond with a simple recipe "
                               "separated by '**Ingredients:**' and '**Instructions:**'."
                },
                {
                    "role": "user",
                    "content": form.query.data,
                }
            ],
            model="llama3-8b-8192",
        )
        recipe_text = chat_completion.choices[0].message.content
        recipe_html = markdown(recipe_text)
        return render_template("ai-recipe.html", form=form, recipe=recipe_html)
    return render_template("ai-recipe.html", form=form)


# TODO disallow user from accessing /register or /login if already logged in or redirect
@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        if user:
            flash("You've already signed up with that email. Log in instead!")
            return redirect("login")
        else:
            secure_password = generate_password_hash(
                form.password.data,
                method="pbkdf2:sha256",
                salt_length=32,
            )
            new_user = User(
                email=form.email.data,
                password=secure_password,
                name=form.name.data,
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for("home"))
    return render_template("register.html", form=form, current_user=current_user)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        if not user:
            flash("That account does not exist, please try again.")
            return redirect(url_for("login"))
        elif not check_password_hash(user.password, form.password.data):
            flash("Password incorrect, please try again.")
            return redirect(url_for("login"))
        else:
            login_user(user)
            return redirect(url_for("home"))
    return render_template("login.html", form=form, current_user=current_user)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
