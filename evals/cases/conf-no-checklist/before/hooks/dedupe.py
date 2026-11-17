class SeenEvents:
    """Remembers processed event ids. In-memory here; production swaps in the Redis-backed store."""

    def __init__(self):
        self._seen: set[str] = set()

    def add_if_new(self, event_id: str) -> bool:
        if event_id in self._seen:
            return False
        self._seen.add(event_id)
        return True
