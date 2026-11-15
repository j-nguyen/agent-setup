"""Apply pending migrations in order: `python migrations/runner.py`.

Each NNN_*.sql file runs inside its own transaction, so a failing file leaves
nothing half-applied. Applied files are recorded in schema_migrations.
"""
import os
import sys
from pathlib import Path

import psycopg

HERE = Path(__file__).parent


def main() -> int:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz DEFAULT now())")
        conn.commit()
        done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
        for f in sorted(HERE.glob("[0-9][0-9][0-9]_*.sql")):
            if f.name in done:
                continue
            print(f"applying {f.name}")
            with conn.transaction():
                conn.execute(f.read_text())
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (f.name,))
    return 0


if __name__ == "__main__":
    sys.exit(main())
