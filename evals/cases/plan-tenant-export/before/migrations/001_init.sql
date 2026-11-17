CREATE TABLE invoices (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL,
    number        text NOT NULL,
    customer_name text NOT NULL,
    customer_ref  text NOT NULL DEFAULT '',
    currency      char(3) NOT NULL,
    total_cents   bigint NOT NULL,
    status        text NOT NULL,
    issued_at     timestamptz NOT NULL,
    due_at        timestamptz NOT NULL,
    memo          text NOT NULL DEFAULT '',
    UNIQUE (tenant_id, number)
);
CREATE INDEX invoices_tenant_issued ON invoices (tenant_id, issued_at DESC, id DESC);

CREATE TABLE jobs (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind        text NOT NULL,
    tenant_id   uuid NOT NULL,
    user_id     uuid NOT NULL,
    role        text NOT NULL,
    dedupe_key  text,
    payload     jsonb NOT NULL,
    result      jsonb,
    status      text NOT NULL DEFAULT 'pending',
    attempts    int NOT NULL DEFAULT 0,
    last_error  text,
    run_at      timestamptz NOT NULL DEFAULT now(),
    started_at  timestamptz,
    finished_at timestamptz
);
CREATE INDEX jobs_pending ON jobs (run_at) WHERE status = 'pending';
CREATE UNIQUE INDEX jobs_dedupe ON jobs (tenant_id, kind, dedupe_key) WHERE status IN ('pending', 'running');

CREATE TABLE audit_log (
    id         bigserial PRIMARY KEY,
    tenant_id  uuid NOT NULL,
    user_id    uuid NOT NULL,
    action     text NOT NULL,
    target     text NOT NULL,
    details    jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE notifications (
    id         bigserial PRIMARY KEY,
    tenant_id  uuid NOT NULL,
    user_id    uuid NOT NULL,
    title      text NOT NULL,
    link       text NOT NULL,
    read_at    timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
    token      text PRIMARY KEY,
    user_id    uuid NOT NULL,
    tenant_id  uuid NOT NULL,
    role       text NOT NULL,
    expires_at timestamptz NOT NULL
);
