import os

WEBHOOK_SECRET = os.environ.get("PROVIDER_WEBHOOK_SECRET", "dev-secret").encode()
LEDGER_URL = os.environ.get("LEDGER_URL", "http://localhost:8081/events")
