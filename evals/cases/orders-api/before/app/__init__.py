from flask import Flask

from app.routes.users import bp as users_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(users_bp)
    return app
