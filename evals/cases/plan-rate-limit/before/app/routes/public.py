"""The partner-facing /v1 API."""
from __future__ import annotations

from app import db
from app.http import Request, Router, error_response, json_response
from app.middleware import handle_errors, require_api_key, with_request_id


def register(router: Router) -> None:
    @router.route("GET", "/v1/status")
    @with_request_id
    def status(request: Request):
        return json_response({"ok": True})

    @router.route("GET", "/v1/products")
    @with_request_id
    @handle_errors
    @require_api_key
    def list_products(request: Request):
        return json_response({"items": db.list_products(request.query.get("category"))})

    @router.route("GET", "/v1/products/<product_id>")
    @with_request_id
    @handle_errors
    @require_api_key
    def get_product(request: Request):
        product = db.get_product(request.params["product_id"])
        if product is None:
            return error_response(404, "not_found", "No such product")
        return json_response(product)
