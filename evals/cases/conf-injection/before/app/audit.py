EVENTS: list[dict] = []


def record(actor_id: int, action: str, detail: dict) -> None:
    EVENTS.append({"actor": actor_id, "action": action, "detail": detail})
