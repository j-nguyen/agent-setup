# Conventions

- Cross-cutting request behavior (auth, request ids, error mapping) lives in
  `app/middleware/` as decorators that wrap a handler. Keep handlers in
  `app/routes/` free of that logic.
- All settings come from environment variables via `app/config.py`. Don't read
  `os.environ` anywhere else.
- Use the shared Redis client from `app/cache.py` (`get_redis()`); don't open
  new connections. Tests swap it for `tests/fakes.FakeRedis` with `set_client`.
- Errors returned to API clients use `app.http.error_response` so the JSON
  shape is always `{"error": {"code": ..., "message": ...}}`.
- Tests: `python3 -m unittest discover -s tests -t .`. Every middleware has its
  own test module.
