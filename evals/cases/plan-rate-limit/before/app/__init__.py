from app.http import Router
from app.routes import dashboard, public


def create_app() -> Router:
    router = Router()
    public.register(router)
    dashboard.register(router)
    return router
