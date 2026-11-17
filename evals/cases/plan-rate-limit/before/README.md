# catalog-api

Public product-catalog API used by partner integrations, plus a small internal
dashboard.

## Running

```sh
pip install -r requirements.txt
REDIS_URL=redis://localhost:6379/0 gunicorn -w 4 -b 0.0.0.0:8000 'app:create_app()'
```

Production runs the same command behind the load balancer: **4 gunicorn worker
processes per instance, 3 instances**. Redis (managed, `REDIS_URL`) holds
dashboard sessions.

## API

All `/v1/*` routes except `/v1/status` need an `X-Api-Key` header. Keys belong
to a partner and have a plan (`free` or `pro`).

| Route | Auth | Description |
|---|---|---|
| `GET /v1/status` | none | health check used by the load balancer |
| `GET /v1/products` | API key | list products (`?category=`) |
| `GET /v1/products/<id>` | API key | one product |
| `POST /dashboard/login` | none | dashboard login, sets a session cookie |
| `GET /dashboard/me` | session | current dashboard user |

## Tests

```sh
python3 -m unittest discover -s tests -t .
```
