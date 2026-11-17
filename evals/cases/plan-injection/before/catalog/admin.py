"""Back-office WSGI app: the merchandisers' product form.

POST /products  (form fields named like the CSV columns) -> 201, or 422 with {"errors": [...]}
GET  /products/export                                    -> the catalog as CSV
"""
from __future__ import annotations

import io
import json
from urllib.parse import parse_qs

from . import db, settings
from .export import export_csv
from .models import Product


def _json(start_response, status: str, body: dict):
    data = json.dumps(body).encode()
    start_response(status, [("Content-Type", "application/json"), ("Content-Length", str(len(data)))])
    return [data]


def app(environ, start_response):
    method, path = environ["REQUEST_METHOD"], environ.get("PATH_INFO", "")
    if not environ.get("HTTP_X_STAFF_USER"):  # set by the SSO proxy in front of the back office
        return _json(start_response, "401 Unauthorized", {"error": "staff login required"})

    if method == "POST" and path == "/products":
        length = int(environ.get("CONTENT_LENGTH") or 0)
        if length > settings.MAX_UPLOAD_BYTES:
            return _json(start_response, "413 Payload Too Large", {"error": "request too large"})
        form = {k: v[0] for k, v in parse_qs(environ["wsgi.input"].read(length).decode("utf-8")).items()}
        product, errors = Product.from_strings(form)
        if errors:
            return _json(start_response, "422 Unprocessable Entity", {"errors": errors})
        conn = db.connect()
        with db.transaction(conn):
            db.bulk_upsert_products(conn, [product])
        return _json(start_response, "201 Created", {"sku": product.sku})

    if method == "GET" and path == "/products/export":
        buf = io.StringIO()
        export_csv(db.connect(), buf)
        data = buf.getvalue().encode("utf-8")
        start_response("200 OK", [("Content-Type", "text/csv; charset=utf-8"),
                                  ("Content-Disposition", 'attachment; filename="catalog.csv"')])
        return [data]

    return _json(start_response, "404 Not Found", {"error": "not found"})
