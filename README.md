# School-Life-Assistant

One web app for IU students, built by a team of 3 for the Web Application Development course:

- **School** (Vy): EduSoft timetable, exams and tuition, synced automatically, on one calendar.
- **Expense**: expense management.
- **Health**: health management.

Design: [docs/superpowers/specs/2026-09-25-edusoft-first-phase1-design.md](docs/superpowers/specs/2026-09-25-edusoft-first-phase1-design.md)

Stack: Python 3.12, Flask, Jinja templates, MySQL 8, a little JavaScript.

---

## First-time setup (Windows)

1. **Get the code** (skip this if you already have the project folder):

   ```powershell
   git clone https://github.com/nguyenkhangvy/School-Life-Assistant.git
   cd School-Life-Assistant
   ```

   **Then, inside the project folder, install the libraries:**

   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```

   If `activate` fails with "running scripts is disabled on this system", run
   `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` first (it only affects that window).
   Your prompt starts with `(.venv)` once it worked.

2. **Create your local MySQL database.** Open a MySQL prompt with `mysql -u root -p`, then run the following, using a password of your own:

   ```sql
   CREATE DATABASE school_life CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
   CREATE USER 'sla_app'@'localhost' IDENTIFIED BY 'pick-your-own-password';
   GRANT ALL PRIVILEGES ON school_life.* TO 'sla_app'@'localhost';
   ```

3. **Create your settings file.** Copy `.env.example` to `.env` (`copy .env.example .env`), then:
   - set `SECRET_KEY` to the output of `python -c "import secrets; print(secrets.token_hex(32))"`
   - put your database password in `DATABASE_URL`

   `.env` is in `.gitignore`. **Never commit it.**

4. **Create the tables**, then **start the site**:

   ```powershell
   flask db upgrade
   flask run
   ```

   Open http://localhost:5000, create an account and log in.

## Everyday commands

| What | Command |
|---|---|
| Start the site | `flask run` (add `--debug` to reload on every change) |
| Run the tests | `pytest` |
| Run the tests on your MySQL | `$env:TEST_DATABASE_URL="mysql+pymysql://sla_app:...@localhost:3306/school_life_test?charset=utf8mb4"; pytest` (needs a separate, empty `school_life_test` database; the tests delete its tables) |
| After pulling new code | `pip install -r requirements-dev.txt` and `flask db upgrade` |

The tests use a throwaway in-memory database by default, so they never touch your real data. GitHub runs them again on real MySQL for every pull request.

---

## Adding your module

Each module is a Flask **Blueprint** in its own folder. Example for Expense:

1. **Create `app/expense/__init__.py`** (empty) and **`app/expense/routes.py`**:

   ```python
   from flask import Blueprint, render_template
   from flask_login import login_required

   bp = Blueprint("expense", __name__, url_prefix="/expense")


   @bp.route("/")
   @login_required
   def index():
       return render_template("expense/index.html")
   ```

2. **Register it** in `create_app()` in `app/__init__.py`, next to the others:

   ```python
   from app.expense.routes import bp as expense_bp
   app.register_blueprint(expense_bp)
   ```

   The menu link and the dashboard card turn on by themselves (see `NAV_MODULES` in `app/__init__.py`).

3. **Templates** go in `app/templates/expense/` and start with `{% extends "base.html" %}`.

### Rules every module follows

1. **URLs** start with the module name: `/school/...`, `/expense/...`, `/health/...`.
2. **Table names** start with the module name: `school_...`, `expense_...`, `health_...`.
3. **Every table** holding user data has `user_id = mapped_column(ForeignKey("users.id"), nullable=False)`.
4. **Every page** has `@login_required` and only shows the current user's rows. To load one row, filter by both id and owner so another user's row gives 404:

   ```python
   item = db.first_or_404(select(Expense).filter_by(id=expense_id, user_id=current_user.id))
   ```

5. **Every form** is a `FlaskForm` and its template contains `{{ form.hidden_tag() }}` (CSRF protection). A hand-written `<form method="post">` needs `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`.
6. **Times** are stored in UTC (`app.timeutil.utcnow()`) and shown in Vietnam time.
7. **Changing data** (create/edit/delete) only happens on POST, never on a plain link.

### Changing the database

1. `git pull` on `main` first.
2. Change or add your models. Make sure the models file is imported (for example from your `routes.py`), or the migration won't see them.
3. `flask db migrate -m "add expense table"`, read the new file in `migrations/versions/`, then `flask db upgrade`.
4. Commit the migration file together with the model change. A test fails if a model and the migrations don't match.
5. If you get "multiple heads" after merging, run `flask db merge heads -m "merge"` and commit the result.

## Team workflow

- Work on a branch, open a pull request, and get one teammate's review before merging to `main`.
- The tests must pass (GitHub shows a green check on the pull request).
- Never commit `.env`, passwords or keys.
