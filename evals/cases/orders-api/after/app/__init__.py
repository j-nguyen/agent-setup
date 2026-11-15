import os

from flask import Flask

from app.routes.orders import bp as orders_bp
from app.routes.users import bp as users_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    app.register_blueprint(users_bp)
    app.register_blueprint(orders_bp)
    return app
