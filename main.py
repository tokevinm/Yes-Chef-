import json
import os
import re
import smtplib
import requests
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from flask import Flask, render_template, redirect, url_for, flash, request, session, send_from_directory, jsonify
from flask_bootstrap import Bootstrap5
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey, Float
from sqlalchemy.types import JSON
from werkzeug.security import generate_password_hash, check_password_hash
from titlecase import titlecase
from groq import Groq
from markdown import markdown
from uuid import uuid4
from forms import RecipeForm, RegisterForm, RegisterCont, LoginForm, AIQueryForm, EditProfileForm, CommentForm, GetRecipeForm

load_dotenv()
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
SMTP_USER = os.environ["SMTP_USERNAME"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]
EDAMAM_API_KEY = os.environ["EDAMAM_API_KEY"]
EDAMAM_APP_ID = os.environ["EDAMAM_APP_ID"]
EDAMAM_ENDPOINT = "https://api.edamam.com/api/nutrition-details"

ALLOWED_URLS = ["allrecipes"]


client = Groq(
    api_key=GROQ_API_KEY,
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ["APP_SECRET_KEY"]
app.config['MAX_CONTENT_LENGTH'] = 2556 * 1179
app.config['RECIPE_PHOTO_FOLDER'] = r'static\images\recipes'
app.config['PROFILE_PHOTO_FOLDER'] = r'static\images\profiles'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

csrf = CSRFProtect(app)
# VITE
CORS(app)
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
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=True)
    image_filepath: Mapped[str] = mapped_column(String(256), nullable=True)
    recipes: Mapped[list["Recipe"]] = relationship(back_populates="author")
    liked_recipes: Mapped[list["Like"]] = relationship(back_populates="user")
    comments: Mapped[list["Comment"]] = relationship(back_populates="comment_author")


class Recipe(db.Model):
    __tablename__ = "recipes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(400), nullable=True)
    ingredients: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    type_diet: Mapped[str] = mapped_column(nullable=True)
    nutrition_facts: Mapped[list["Nutrition"]] = relationship(back_populates="recipe", cascade="all, delete-orphan")
    default_servings: Mapped[int] = mapped_column(Integer, nullable=False)
    time_to_cook: Mapped[str] = mapped_column(String, nullable=True)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    author: Mapped["User"] = relationship(back_populates="recipes")
    liked_by_users: Mapped[list["Like"]] = relationship(back_populates="recipe", cascade="all, delete-orphan")
    comments: Mapped[list["Comment"]] = relationship(back_populates="recipe", cascade="all, delete-orphan")
    image_filepath: Mapped[str] = mapped_column(String(256), nullable=True)
    # Users don't have to upload a photo for now.
    # Make so that won't show up on front page if no photo? (Warn when creating recipe)
    image_url: Mapped[str] = mapped_column(nullable=True)
    recipe_url: Mapped[str] = mapped_column(unique=True, nullable=True)
    recipe_source: Mapped[str] = mapped_column(nullable=True)


class Nutrition(db.Model):
    __tablename__ = "nutrition facts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(Integer, ForeignKey("recipes.id"), nullable=False)
    recipe: Mapped["Recipe"] = relationship(back_populates="nutrition_facts")
    nutrient: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    daily_value_percent: Mapped[int] = mapped_column(Integer, nullable=True)


class Like(db.Model):
    __tablename__ = "likes"
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
    user: Mapped["User"] = relationship(back_populates="liked_recipes")
    recipe_id: Mapped[int] = mapped_column(Integer, ForeignKey("recipes.id"), primary_key=True)
    recipe: Mapped["Recipe"] = relationship(back_populates="liked_by_users")


class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    comment_author: Mapped["User"] = relationship(back_populates="comments")
    recipe_id: Mapped[int] = mapped_column(Integer, ForeignKey("recipes.id"))
    recipe: Mapped["Recipe"] = relationship(back_populates="comments")


with app.app_context():
    db.create_all()


@app.route("/")
def home():
    result = db.session.execute(db.select(Recipe))
    recipes = result.scalars().all()[::-1]

    likes = {}
    if current_user.is_authenticated:
        for recipe in recipes:
            # Check if the user has liked this recipe
            liked = any(like.user_id == current_user.id for like in recipe.liked_by_users)
            likes[recipe.id] = liked
    return render_template("index.html", recipes=recipes, likes=likes)


# TODO fix ingredients/change form to allow for list[dict]
@app.route("/add-recipe", methods=['GET', 'POST'])
def add_recipe():

    if not current_user.is_authenticated:
        return redirect(url_for("home"))

    form = RecipeForm(
        ingredients="<ul><li></li></ul>",
        instructions="<ol><li></li></ol>"
    )

    if form.validate_on_submit():

        form = RecipeForm(
            title=form.title.data,
            description=form.description.data,
            ingredients=form.ingredients.data,
            instructions=form.instructions.data,
            servings=form.servings.data,
            time_hours=form.time_hours.data,
            time_mins=form.time_mins.data,
            type_diet=form.type_diet.data,
            image_url=form.image_url.data,
        )

        title_input = form.title.data
        title_result = db.session.execute(db.select(Recipe).where(Recipe.title == title_input)).scalar()
        if title_result:
            flash("Recipe Name already exists :( Try something spicier, like \"Kevin's Hot and Sexy Chicken!\"")
            return render_template("add-recipe.html", form=form)

        ingredients_html = BeautifulSoup(form.ingredients.data, 'html.parser').prettify()
        target_ingredients_parsed = BeautifulSoup("<ul><li>&nbsp;</li></ul>", 'html.parser').prettify()
        if ingredients_html == target_ingredients_parsed:
            flash("Every recipe needs some <em>ingredients</em>!")
            return render_template("add-recipe.html", form=form)

        instructions_html = BeautifulSoup(form.instructions.data, 'html.parser').prettify()
        target_instructions_parsed = BeautifulSoup("<ol><li>&nbsp;</li></ol>", 'html.parser').prettify()
        if instructions_html == target_instructions_parsed:
            flash("Don't forget <em>instructions</em> on how to recreate your masterpiece!")
            return render_template("add-recipe.html", form=form)

        filepath = None
        image_url = None
        if form.image_upload.data:
            uploaded_file = form.image_upload.data
            image_uuid = uuid_from_filename(uploaded_file.filename)
            filepath = "images/recipes/" + image_uuid
            uploaded_file.save(os.path.join(app.config['RECIPE_PHOTO_FOLDER'], image_uuid))
        elif form.image_url.data:
            image_url = form.image_url.data

        total_time = ""
        if form.time_hours.data:
            total_time += f"{form.time_hours.data} hr "
        if form.time_mins.data:
            total_time += f"{form.time_mins.data} mins"
        total_time = total_time.strip()

        diets_string = ", ".join(form.type_diet.data)

        new_recipe = Recipe(
            title=form.title.data,
            description=form.description.data,
            ingredients=form.ingredients.data,
            instructions=form.instructions.data,
            default_servings=form.servings.data,
            time_to_cook=total_time,
            type_diet=diets_string,
            author=current_user,
            image_filepath=filepath,
            image_url=image_url,
        )

        db.session.add(new_recipe)
        db.session.commit()

        ingredients_list = markup_to_list(form.ingredients.data)
        edamam_ingredients = oil_converter(form.title.data, ingredients_list)
        edamam_data = edamam_nutrition_analysis(form.title.data, edamam_ingredients)
        nutrition_to_db(new_recipe, edamam_data["totalNutrients"], edamam_data["totalDaily"])

        return redirect(url_for("display_recipe", recipe_title=form.title.data))

    return render_template("add-recipe.html", form=form)


# TODO Add "Delete Comment" functionality
@app.route("/recipe/<string:recipe_title>", methods=["GET", "POST"])
def display_recipe(recipe_title):
    recipe = Recipe.query.filter(Recipe.title == recipe_title).first()
    likes = Like.query.filter(Like.recipe_id == recipe.id).all()
    nutrients = NutritionFacts(recipe.id)

    # ingredients = "<ul> "
    # ing_list = recipe.ingredients
    # for ing in ing_list:
    #     ing_full = f"{ing["amount"]} {ing["unit"]} {ing["ingredient"]}"
    #     ingredients += f"<li>{ing_full}</li> "
    # ingredients += "</ul>"

    recipe_url = None
    recipe_source = None
    if recipe.recipe_url:
        recipe_url = "https://www." + recipe.recipe_url
        recipe_domain_name = recipe.recipe_url.split(".com")[0]
        if recipe_domain_name == "allrecipes":
            recipe_source = "images/sources/allrecipes.svg"

    current_user_liked = False
    if current_user.is_authenticated:
        for like in recipe.liked_by_users:
            if current_user.id == like.user_id:
                current_user_liked = True

    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=comment_form.body.data,
            comment_author=current_user,
            recipe=recipe
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for("display_recipe", recipe_title=recipe_title))

    return render_template(
        "recipe.html",
        recipe=recipe,
        # ingredients=ingredients,
        nutrients=nutrients,
        recipe_source=recipe_source,
        recipe_url=recipe_url,
        current_user=current_user,
        likes=likes,
        currently_liked=current_user_liked,
        comment_form=comment_form
    )


@app.route("/like/<int:recipe_id>", methods=["POST"])
def like_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    like = Like.query.filter_by(user_id=current_user.id, recipe_id=recipe.id).first()
    if like:
        db.session.delete(like)
        db.session.commit()
        return jsonify({"status": "unliked", "likes_count": len(recipe.liked_by_users)})
    else:
        new_like = Like(user=current_user, recipe=recipe)
        db.session.add(new_like)
        db.session.commit()
        return jsonify({"status": "liked", "likes_count": len(recipe.liked_by_users)})


@app.route("/edit-recipe/<string:recipe_title>", methods=["GET", "POST"])
def edit_recipe(recipe_title):
    recipe = Recipe.query.filter(Recipe.title == recipe_title).first()
    if current_user.id != recipe.author_id:
        return redirect(url_for("home"))

    if recipe.type_diet:
        type_diet_formatted = recipe.type_diet.split(", ")
    else:
        type_diet_formatted = None

    edit_form = RecipeForm(
        title=recipe.title,
        description=recipe.description,
        ingredients=recipe.ingredients,
        instructions=recipe.instructions,
        type_diet=type_diet_formatted,
        image_url=recipe.image_url,
    )
    # TODO add a "delete image" function Instead of only overwriting?? Also how to show on edit_form
    #  that image file already exists? FlaskForm doesn't allow prepopulating for security reasons

    if edit_form.validate_on_submit():

        filepath = recipe.image_filepath
        image_url = recipe.image_url
        if edit_form.image_upload.data:
            uploaded_file = edit_form.image_upload.data
            image_uuid = uuid_from_filename(uploaded_file.filename)
            filepath = "images/recipes/" + image_uuid
            if recipe.image_filepath:
                os.remove(f"static/{recipe.image_filepath}")
            uploaded_file.save(os.path.join(app.config['RECIPE_PHOTO_FOLDER'], image_uuid))
        elif edit_form.image_url.data:
            image_url = edit_form.image_url.data

        diets_string = ", ".join(edit_form.type_diet.data)

        recipe.title = edit_form.title.data
        recipe.description = edit_form.description.data
        recipe.ingredients = edit_form.ingredients.data
        recipe.instructions = edit_form.instructions.data
        recipe.type_diet = diets_string
        recipe.image_filepath = filepath
        recipe.image_url = image_url
        db.session.commit()

        Nutrition.query.filter_by(recipe_id=recipe.id).delete()

        ingredients_list = markup_to_list(edit_form.ingredients.data)
        edamam_ingredients = oil_converter(edit_form.title.data, ingredients_list)
        edamam_data = edamam_nutrition_analysis(edit_form.title.data, edamam_ingredients)
        nutrition_to_db(recipe, edamam_data["totalNutrients"], edamam_data["totalDaily"])

        return redirect(url_for("display_recipe", recipe_title=recipe.title))

    return render_template(
        "add-recipe.html",
        form=edit_form,
        editing=True,
        recipe_title=recipe.title,
        current_user=current_user
    )


@app.route("/delete/<int:recipe_id>")
def delete_recipe(recipe_id):
    recipe_to_delete = db.get_or_404(Recipe, recipe_id)
    db.session.delete(recipe_to_delete)
    db.session.commit()
    return redirect(url_for("home"))


@app.route("/search")
def search_recipe():
    search_param = request.args.get('query')
    recipes = None
    if search_param:
        formatted_param = re.sub(r'[^a-zA-Z0-9\- ]', "", search_param)
        param_list = formatted_param.split()
        recipe_list = []
        # TODO ? Add "description" to what is searched?
        for substring in param_list:
            title_results = Recipe.query.filter(Recipe.title.like(f'%{substring}%')).all()
            recipe_list.extend(title_results)
            ingredients_results = Recipe.query.filter(Recipe.ingredients.like(f'%{substring}%')).all()
            recipe_list.extend(ingredients_results)
            instructions_results = Recipe.query.filter(Recipe.instructions.like(f'%{substring}%')).all()
            recipe_list.extend(instructions_results)
        recipes = list(dict.fromkeys(recipe_list))[::-1]
    return render_template("search.html",
                           search_param=search_param,
                           recipes=recipes,
                           )


@app.route("/ai-recipe", methods=["GET", "POST"])
def ai_recipe():
    form = AIQueryForm()
    if form.validate_on_submit():
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a chef with knowledge in every culture and cuisine. Use only "
                               "user provided and common household ingredients to respond with a recipe "
                               "with the name of the recipe in bold, separated by '**Description:**', "
                               "'**Number of Servings:**', '**Ingredients:**', and '**Instructions:**'."
                },
                {
                    "role": "user",
                    "content": form.query.data,
                }
            ],
            model="llama3-8b-8192",
        )
        recipe_text = chat_completion.choices[0].message.content
        # recipe_text is  split and saved to session to be saved in save_ai_recipe()
        recipe_html = markdown(recipe_text)
        # recipe_html is displayed directly to the ai-recipe page

        title = recipe_text.split("**")[1]
        recipe_split1 = recipe_text.split("**Instructions:**")
        instructions = recipe_split1[1].strip()
        recipe_split2 = recipe_split1[0].split("**Ingredients:**")
        ingredients = recipe_split2[1].strip()
        recipe_split3 = recipe_split2[0].split("**Number of Servings:**")
        num_servings = recipe_split3[1].strip()[0]
        recipe_split4 = recipe_split3[0].split("**Description:**")
        description = recipe_split4[1].strip()

        session['ai_recipe'] = {
            'title': title,
            'description': description,
            'servings': num_servings,
            'ingredients': ingredients,
            'instructions': instructions
        }

        return render_template("ai-recipe.html", form=form, recipe=recipe_html, ai_recipe_gen=True)
    return render_template("ai-recipe.html", form=form)


# TODO fix save_ai_recipe() for ingredients list[dict]
@app.route("/save-ai-recipe", methods=["POST"])
def save_ai_recipe():
    if not current_user.is_authenticated:
        return redirect(url_for("home"))

    recipe = session.get('ai_recipe')
    if not recipe:
        flash("No AI-generated recipe to save!")
        return redirect(url_for("ai_recipe"))

    title = recipe['title']
    description = recipe['description']
    servings = recipe['servings']
    ingredients = markdown(recipe['ingredients'])
    instructions = markdown(recipe['instructions'])

    existing_recipe = Recipe.query.filter_by(title=title).first()
    if existing_recipe:
        flash("A recipe with this title already exists.")
        return redirect(url_for("ai_recipe"))

    new_recipe = Recipe(
        title=title,
        description=description,
        default_servings=servings,
        ingredients=ingredients,
        instructions=instructions,
        author=current_user,
    )

    db.session.add(new_recipe)
    db.session.commit()

    ingredients_list = markup_to_list(ingredients)
    edamam_ingredients = oil_converter(title, ingredients_list)
    edamam_data = edamam_nutrition_analysis(title, edamam_ingredients)
    nutrition_to_db(new_recipe, edamam_data["totalNutrients"], edamam_data["totalDaily"])

    return redirect(url_for("display_recipe", recipe_title=title))


# TODO add more websites to webscrape capabilities
@app.route("/recipe-saver", methods=["GET", "POST"])
def recipe_saver():
    if not current_user.is_authenticated:
        return redirect(url_for("home"))

    recipe_url_form = GetRecipeForm()

    if recipe_url_form.validate_on_submit():

        split_url = None
        url_www_split = recipe_url_form.recipe_url.data.split("www.")
        if len(url_www_split) == 1:
            split_url = url_www_split[0]
        elif len(url_www_split) == 2:
            split_url = url_www_split[1]

        url_com_split = split_url.split(".com")
        if url_com_split[0] not in ALLOWED_URLS:
            flash(f"Functionality for {url_com_split[0]} has not been integrated yet")
            return redirect(url_for("recipe_saver"))
        # elif url_com_split[0] == "allrecipes":
        #     pass

        recipe_url_result = Recipe.query.filter(Recipe.recipe_url == split_url).first()
        if recipe_url_result:
            flash(f"Someone has already saved that recipe! Try searching for it instead")
            return redirect(url_for("recipe_saver"))

        response = requests.get(recipe_url_form.recipe_url.data)
        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.find("h1", {"class": "article-heading"}).text
        description = soup.find("p", {"class": "article-subheading"}).text

        ingredients = []
        ing_list = soup.find_all('li', {'class': 'mm-recipes-structured-ingredients__list-item'})
        for ing in ing_list:
            ing_components = {"amount": ing.find("span", {"data-ingredient-quantity": "true"}).text,
                              "unit": ing.find("span", {"data-ingredient-unit": "true"}).text,
                              "ingredient": ing.find("span", {"data-ingredient-name": "true"}).text}
            ingredients.append(ing_components)

        instructions = "<ol> "
        instructions_soup = soup.find_all("li", {
            "class": "comp mntl-sc-block mntl-sc-block-startgroup mntl-sc-block-group--LI"})
        for step in instructions_soup:
            step_text = step.find("p").text
            instructions += f"<li>{step_text}</li> "
        instructions += f"</ol>"

        recipe_details = soup.find_all(class_="mm-recipes-details__item")
        total_time = None
        num_servings = None
        for detail in recipe_details:
            label = detail.find(class_='mm-recipes-details__label')
            value = detail.find(class_='mm-recipes-details__value')
            if label and "Total Time:" in label.text:
                total_time = value.text.strip()
                continue
            if label and "Servings" in label.text:
                num_servings = value.text.strip()  # Get the text and strip any extra whitespace
                continue

        image = soup.find("img", {"class": "primary-image__image"})
        if image:
            image_url = image["src"]
        # What about 'class': 'universal-image__image'? Reason I didn't use as secondary option?
        else:
            image = soup.find("img", {"id": "mntl-sc-block-image_1-0"})
            image_url = image["data-hi-res-src"]

        new_recipe = Recipe(
            title=title,
            description=description,
            ingredients=ingredients,
            instructions=instructions,
            default_servings=num_servings,
            time_to_cook=total_time,
            author=current_user,
            image_url=image_url,
            recipe_url=split_url,
            recipe_source=url_com_split[0]
        )
        db.session.add(new_recipe)
        db.session.commit()

        ingredients_list = []
        for ing in ingredients:
            ingredient = f"{ing["amount"]} {ing["unit"]} {ing["ingredient"]}"
            ingredients_list.append(ingredient)

        print(ingredients_list)
        # ingredients_list = markup_to_list(ingredients)
        edamam_ingredients = oil_converter(title, ingredients_list)
        edamam_data = edamam_nutrition_analysis(title, edamam_ingredients)
        nutrition_to_db(new_recipe, edamam_data["totalNutrients"], edamam_data["totalDaily"])

        return redirect(url_for("display_recipe", recipe_title=title))
    return render_template("recipe-saver.html", form=recipe_url_form)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        message = request.form["message"]
        send_email(name, email, phone, message)
    return render_template("contact.html")


def send_email(name, email, phone, message):
    with smtplib.SMTP(host="smtp.gmail.com", port=587) as connection:
        connection.starttls()
        connection.login(
            user=SMTP_USER,
            password=SMTP_PASSWORD,
        )
        connection.sendmail(
            from_addr=SMTP_USER,
            to_addrs=SMTP_USER,
            msg=f"Subject:New Message!\n\n Name: {name}\n Email: {email}\n Phone: {phone}\n Message: {message}"
        )


@app.route("/user/<string:user_name>")
def display_profile(user_name):
    user = User.query.filter(User.name == user_name).first()
    user_recipes = Recipe.query.filter(Recipe.author_id == user.id).all()[::-1]

    liked_recipes = []
    if user_name == current_user.name:
        liked_recipes = db.session.query(Recipe).join(Like).filter(Like.user_id == current_user.id).all()[::-1]
    return render_template("profile.html", user=user, recipes=user_recipes, liked_recipes=liked_recipes)


@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():
    profile_edit_form = EditProfileForm()
    if profile_edit_form.validate_on_submit():
        if profile_edit_form.name.data != "":
            current_user.name = profile_edit_form.name.data
        if profile_edit_form.email.data != "":
            current_user.email = profile_edit_form.email.data
        if profile_edit_form.password.data != "":
            current_user.password = profile_edit_form.password.data
        if profile_edit_form.description.data != "":
            current_user.description = profile_edit_form.description.data
        if profile_edit_form.image_upload.data:
            uploaded_file = profile_edit_form.image_upload.data
            image_uuid = uuid_from_filename(uploaded_file.filename)
            filepath = "images/profiles/" + image_uuid
            if current_user.image_filepath:
                os.remove(f"static/{current_user.image_filepath}")
            uploaded_file.save(os.path.join(app.config['PROFILE_PHOTO_FOLDER'], image_uuid))
            current_user.image_filepath = filepath
        db.session.commit()
        return redirect(url_for("display_profile", user_name=current_user.name))
    return render_template(
        "register.html",
        form=profile_edit_form,
        current_user=current_user
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    form = RegisterForm()
    if form.validate_on_submit():
        user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        if user:
            flash("You've already signed up with that email. Log in instead!")
            return redirect(url_for("login"))
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
            return redirect(url_for("register2"))
    return render_template("register.html", form=form, current_user=current_user)


# Additional user profile info after registration; can it be done better?
@app.route("/register-2", methods=["GET", "POST"])
def register2():
    if not current_user.is_authenticated:
        return redirect(url_for("home"))
    form = RegisterCont()
    if form.validate_on_submit():
        current_user.description = form.description.data
        if form.image_upload.data:
            uploaded_file = form.image_upload.data
            image_uuid = uuid_from_filename(uploaded_file.filename)
            filepath = "images/profiles/" + image_uuid
            if current_user.image_filepath:  # Shouldn't for new users but 'edge case' if they're reaccessing this page
                os.remove(f"static/{current_user.image_filepath}")
            uploaded_file.save(os.path.join(app.config['PROFILE_PHOTO_FOLDER'], image_uuid))
            current_user.image_filepath = filepath
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("register2.html", form=form, current_user=current_user)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
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


# REACT/VITE (?)
@app.route('/api/data')
def get_data():
    return jsonify({"message": "Hello from Flask!"})


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')


def uuid_from_filename(filename):
    """Generates a UUID from an image's filename/extension to be saved as"""

    split_filename = filename.split(".")
    file_extension = split_filename[-1]
    return str(uuid4()) + "." + file_extension


def markup_to_list(markup_ingredients: str) -> list[str]:
    """Reformats ingredients from markup (which they're inputted and saved as to the database)
    to a List to be parsed through and analyzed"""

    ingredients_no_ul = re.sub(r"</?ul>", "", markup_ingredients)
    ingredients_no_o_li = re.sub(r"<li>", "", ingredients_no_ul)
    ingredients_list = [ing.strip() for ing in ingredients_no_o_li.split("</li>")]
    return ingredients_list


def oil_converter(title: str, ingredients: list[str]) -> list[str]:
    """Takes a recipe's title and a List of its ingredients as inputs to determine whether
    the amount of oil used needs to be altered to get a more accurate nutritional value calculation
    based on how the oil is used i.e. deep-frying vs. being made into a dressing/vinaigrette"""

    if ("dressing" or "vinaigrette") in title.lower():
        return ingredients

    target_units = ["quart", "qt", "cup", "quarts", "qts", "cups"]
    num_str_to_int = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10
    }

    for i, ing in enumerate(ingredients):

        if re.search(r'\boil\b', ing.lower()) and any(unit in ing.lower() for unit in target_units):
            ing_split = ing.strip().split(" ")
            ing_number = re.search(r'\d+(\.\d+)?', ing_split[0])
            ing_unit = re.search(r'(quart|qt|cup|quarts|qts|cups)', ing_split[0], re.IGNORECASE)

            if ing_number and not ing_unit:
                # ex. "1 cup"
                new_amount = float(ing_number.group()) * 0.15
                ing_split[0] = str(new_amount)
            elif ing_number and ing_unit:
                # ex. "1cup"
                new_amount = float(ing_number.group()) * 0.15
                ing_split[0] = f"{str(new_amount)} {ing_unit.group()}"
            elif not ing_number:
                # ex. "one cup"
                amount = num_str_to_int[ing_split[0]]
                new_amount = amount * 0.15
                ing_split[0] = str(new_amount)
            ingredients[i] = " ".join(ing_split)

        if ing == "&nbsp;" or ing == "":
            ingredients.pop(i)

    return ingredients


def edamam_nutrition_analysis(title: str, ingredients: list[str]) -> dict:
    """Takes the title and ingredients of a recipe to send a post request to the Edamam API
    to analyze the recipe for its nutritional value"""

    edamam_params = {
        "app_id": EDAMAM_APP_ID,
        "app_key": EDAMAM_API_KEY
    }
    recipe_data = {
        "title": title,
        "ingr": ingredients
    }
    response = requests.post(
        url=EDAMAM_ENDPOINT,
        params=edamam_params,
        headers={"Content-Type": "application/json"},
        data=json.dumps(recipe_data)
    )

    response.raise_for_status()
    data = response.json()
    return data


def nutrition_to_db(recipe: Recipe, nutrition_dict: dict, daily_value_dict: dict):
    """Takes a recipe and its Edamam API generated dictionaries as inputs and
    stores all Nutrition Facts related nutrients to the Nutrition table within the SQLite database.
    Follows FDA rounding guidelines for each nutrient group."""

    non_label = ["CHOCDF.net", "WATER", "MG", "ZN", "P", "VITA_RAE", "VITC", "THIA", "RIBF",
                 "NIA", "VITB6A", "FOLDFE", "FOLFD", "FOLAC", "VITB12", "TOCPHA", "VITK1"]

    for nutrient, data in nutrition_dict.items():
        if nutrient not in non_label:

            amount = data["quantity"]/int(recipe.default_servings)

            if nutrient in ["ENERC_KCAL"]:
                if amount < 5:
                    amount = 0
                elif 5 <= amount <= 50:
                    amount = 5 * round(amount / 5)
                else:
                    amount = 10 * round(amount / 10)
            elif nutrient in ["FAT", "FASAT", "FATRN", "FAMS", "FAPU"]:
                if amount < 0.5:
                    amount = 0
                elif 0.5 <= amount < 5:
                    amount = round(amount * 2) / 2
                else:
                    amount = round(amount)
            elif nutrient in ["CHOLE"]:
                if amount < 2:
                    amount = 0
                elif 2 <= amount <= 5:
                    amount = round(amount)
                else:
                    amount = 5 * round(amount / 5)
            elif nutrient in ["NA", "K"]:
                if amount < 5:
                    amount = 0
                elif 5 <= amount <= 140:
                    amount = 5 * round(amount / 5)
                else:
                    amount = 10 * round(amount / 10)
            elif nutrient in ["CHOCDF", "FIBTG", "SUGAR"]:
                if amount < 0.5:
                    amount = 0
                elif 0.5 <= amount < 1:
                    amount = round(amount, 1)
                else:
                    amount = round(amount)
            elif nutrient in ["PROCNT"]:
                if amount < 0.5:
                    amount = 0
                else:
                    amount = round(amount)
            elif nutrient in ["FE", "VITD"]:
                amount = round(amount, 1)
            elif nutrient in ["CA"]:
                amount = 10 * round(amount / 10)

            try:
                dvp = int(daily_value_dict[nutrient].get("quantity", None))
            except KeyError:
                dvp = None

            new_nutrition = Nutrition(
                recipe=recipe,
                nutrient=nutrient,
                amount=amount,
                unit=data["unit"],
                daily_value_percent=dvp
            )
            db.session.add(new_nutrition)

    db.session.commit()


class NutritionFacts:
    """Saves each of the recipe's important nutrients as an object to be able to access amount, unit, and DVP"""
    def __init__(self, recipe_id):
        self.kcal = Nutrition.query.filter_by(recipe_id=recipe_id, nutrient="ENERC_KCAL").first()
        self.totalfat = Nutrition.query.filter_by(recipe_id=recipe_id, nutrient="FAT").first()
        self.satfat = Nutrition.query.filter_by(recipe_id=recipe_id, nutrient="FASAT").first()
        self.transfat = Nutrition.query.filter_by(recipe_id=recipe_id, nutrient="FATRN").first()
        self.cholesterol = Nutrition.query.filter_by(recipe_id=recipe_id, nutrient="CHOLE").first()
        self.sodium = Nutrition.query.filter_by(recipe_id=recipe_id, nutrient="NA").first()
        self.totalcarbs = Nutrition.query.filter_by(recipe_id=recipe_id, nutrient="CHOCDF").first()
        self.fiber = Nutrition.query.filter_by(recipe_id=recipe_id, nutrient="FIBTG").first()
        self.sugar = Nutrition.query.filter_by(recipe_id=recipe_id, nutrient="SUGAR").first()
        self.protein = Nutrition.query.filter_by(recipe_id=recipe_id, nutrient="PROCNT").first()
        self.vitd = Nutrition.query.filter_by(recipe_id=recipe_id, nutrient="VITD").first()
        self.calcium = Nutrition.query.filter_by(recipe_id=recipe_id, nutrient="CA").first()
        self.iron = Nutrition.query.filter_by(recipe_id=recipe_id, nutrient="FE").first()
        self.potassium = Nutrition.query.filter_by(recipe_id=recipe_id, nutrient="K").first()


if __name__ == "__main__":
    app.run(debug=True)
