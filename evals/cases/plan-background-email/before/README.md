# shopfront

Backend for the shopfront web app: accounts, billing and transactional email.
Django-style layout, but plain Python + SQL (Postgres in production, SQLite in tests).

## Processes

| Process | Command | What it does |
|---|---|---|
| web | `gunicorn shopfront.wsgi -w 4` | HTTP API |
| worker | `python -m jobs.worker` | runs background jobs from the `jobs` table (2 replicas) |

## Tests

```sh
python3 -m unittest discover -s tests -t .
```
