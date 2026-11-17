"""Tiny migration runner.

Each file in migrations/ runs in its own transaction, in filename order. A file whose
first line is `-- migrate: no-transaction` runs in autocommit mode instead (needed for
CREATE INDEX CONCURRENTLY, which Postgres refuses to run inside a transaction).
"""
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"
NO_TX_MARKER = "-- migrate: no-transaction"


def pending(applied: set[str]) -> list[Path]:
    return [p for p in sorted(MIGRATIONS.glob("*.sql")) if p.name not in applied]


def run(conn, applied: set[str]) -> list[str]:
    done = []
    for path in pending(applied):
        sql = path.read_text()
        if sql.startswith(NO_TX_MARKER):
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.autocommit = False
        else:
            with conn:  # psycopg: commit on success, roll back on error
                with conn.cursor() as cur:
                    cur.execute(sql)
        with conn, conn.cursor() as cur:
            cur.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
        done.append(path.name)
    return done
