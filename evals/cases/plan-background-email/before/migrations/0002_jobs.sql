CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,              -- JSON
    status TEXT NOT NULL DEFAULT 'queued', -- queued | running | done | dead
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    run_at REAL NOT NULL,               -- unix time
    last_error TEXT,
    dedupe_key TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS jobs_due ON jobs (status, run_at);
