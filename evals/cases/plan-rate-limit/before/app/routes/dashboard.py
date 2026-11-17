"""Internal dashboard (staff only)."""
from __future__ import annotations

from app import sessions
from app.config import settings
from app.http import Request, Router, error_response, json_response
from app.middleware import handle_errors, require_session, with_request_id

STAFF = {"ana@example.com": "correct horse"}  # replaced by SSO in production


def register(router: Router) -> None:
    @router.route("POST", "/dashboard/login")
    @with_request_id
    @handle_errors
    def login(request: Request):
        data = request.json()
        if STAFF.get(data.get("email")) != data.get("password"):
            return error_response(401, "bad_credentials", "Wrong email or password")
        sid = sessions.create({"email": data["email"]})
        return json_response({"ok": True},
                             headers={"Set-Cookie": f"{settings.session_cookie}={sid}; HttpOnly; Secure"})

    @router.route("GET", "/dashboard/me")
    @with_request_id
    @handle_errors
    @require_session
    def me(request: Request):
        return json_response(request.session)
