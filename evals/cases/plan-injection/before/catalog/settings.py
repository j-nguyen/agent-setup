"""Limits and configuration, overridable through environment variables."""
import os

DB_PATH = os.environ.get("CATALOG_DB", "catalog.sqlite3")

# Rows written per executemany() call in bulk operations.
BULK_BATCH_SIZE = int(os.environ.get("CATALOG_BULK_BATCH_SIZE", "500"))

# Exports stream rows from the cursor in chunks of this size.
EXPORT_CHUNK_SIZE = int(os.environ.get("CATALOG_EXPORT_CHUNK_SIZE", "1000"))

# Upper bound on any file the back office accepts from a user.
MAX_UPLOAD_BYTES = int(os.environ.get("CATALOG_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
