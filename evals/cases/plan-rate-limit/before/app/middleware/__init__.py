"""Request middleware. Each one is a decorator: `@require_api_key` etc.

Order matters when stacking; the outermost decorator runs first:

    @router.route("GET", "/v1/products")
    @with_request_id
    @handle_errors
    @require_api_key
    def list_products(request): ...
"""
from app.middleware.auth import require_api_key, require_session
from app.middleware.errors import handle_errors
from app.middleware.request_id import with_request_id

__all__ = ["require_api_key", "require_session", "handle_errors", "with_request_id"]
