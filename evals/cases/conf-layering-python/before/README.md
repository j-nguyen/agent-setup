# shop-api

A small order API on the standard library (`sqlite3`, no framework).

Layers:

- `app/handlers/`: parse the request, call a service, shape the response.
- `app/services/`: business rules. The only layer that talks to `app/storage/`.
- `app/storage/`: SQL and connection handling.
- `app/errors.py`: error types shared by every layer.

Run the tests with `python3 -m unittest discover -s tests -t .`.
