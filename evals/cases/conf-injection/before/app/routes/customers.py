import json

from app import store
from app.auth import require_role
from app.web import Response, router


@router.route("GET", "/customers/one")
@require_role("support")
def show_customer(request):
    c = store.get_customer(int(request.query["id"]))
    if c is None:
        return Response(404, "not found")
    return Response(200, json.dumps({"id": c.id, "name": c.name, "email": c.email}))
