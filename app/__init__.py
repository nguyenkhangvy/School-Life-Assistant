from flask import Flask

from app.config import load_config
from app.extensions import csrf, db, login_manager, migrate

# Menu entries in base.html. A module's link turns on once its blueprint is
# registered below; until then it is shown as "coming soon".
NAV_MODULES = [
    ("School", "school.index"),
    ("Expense", "expense.index"),
    ("Health", "health.index"),
]


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(config if config is not None else load_config())

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    csrf.init_app(app)

    from app.auth.routes import bp as auth_bp
    from app.main.routes import bp as main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    @app.context_processor
    def inject_nav_items():
        return {
            "nav_items": [
                {"label": label, "endpoint": endpoint if endpoint in app.view_functions else None}
                for label, endpoint in NAV_MODULES
            ]
        }

    return app
