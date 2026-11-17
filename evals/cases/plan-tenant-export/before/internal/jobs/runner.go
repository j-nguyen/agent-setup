// Package jobs is the background job runner. Jobs are rows in the jobs table,
// claimed with FOR UPDATE SKIP LOCKED, retried with backoff, and run with the
// enqueuing user's Principal restored into the context, so tenant-scoped
// repositories work unchanged inside a job.
package jobs

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log/slog"
	"time"

	"example.com/ledgerly/internal/auth"
)

type Handler func(ctx context.Context, payload json.RawMessage) error

type Runner struct {
	DB          *sql.DB
	handlers    map[string]Handler
	MaxAttempts int
}

func NewRunner(db *sql.DB) *Runner {
	return &Runner{DB: db, handlers: map[string]Handler{}, MaxAttempts: 5}
}

// Register adds a handler for a job kind. Call before Start.
func (r *Runner) Register(kind string, h Handler) {
	if _, dup := r.handlers[kind]; dup {
		panic("jobs: duplicate kind " + kind)
	}
	r.handlers[kind] = h
}

// Enqueue stores a job for the caller's tenant and user. dedupeKey, if not empty,
// makes enqueueing idempotent: a second job with the same key for the same tenant
// returns the existing job's ID while it's still pending or running.
func (r *Runner) Enqueue(ctx context.Context, kind, dedupeKey string, payload any) (string, error) {
	p, err := auth.FromContext(ctx)
	if err != nil {
		return "", err
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}
	var id string
	err = r.DB.QueryRowContext(ctx, `
		INSERT INTO jobs (kind, tenant_id, user_id, role, dedupe_key, payload)
		VALUES ($1, $2, $3, $4, NULLIF($5, ''), $6)
		ON CONFLICT (tenant_id, kind, dedupe_key) WHERE status IN ('pending', 'running')
		DO UPDATE SET kind = EXCLUDED.kind
		RETURNING id`, kind, p.TenantID, p.UserID, string(p.Role), dedupeKey, body).Scan(&id)
	return id, err
}

// Status reports a job's state for the caller's tenant ("pending", "running", "done", "failed").
func (r *Runner) Status(ctx context.Context, id string) (status string, result json.RawMessage, err error) {
	p, err := auth.FromContext(ctx)
	if err != nil {
		return "", nil, err
	}
	err = r.DB.QueryRowContext(ctx,
		`SELECT status, COALESCE(result, 'null') FROM jobs WHERE id = $1 AND tenant_id = $2`,
		id, p.TenantID).Scan(&status, &result)
	return status, result, err
}

type job struct {
	id, kind, tenantID, userID, role string
	payload                          json.RawMessage
	attempts                         int
}

// Start polls for work until ctx is cancelled.
func (r *Runner) Start(ctx context.Context, workers int) {
	for i := 0; i < workers; i++ {
		go func() {
			for ctx.Err() == nil {
				if !r.runOne(ctx) {
					select {
					case <-ctx.Done():
					case <-time.After(time.Second):
					}
				}
			}
		}()
	}
}

func (r *Runner) runOne(ctx context.Context) bool {
	var j job
	err := r.DB.QueryRowContext(ctx, `
		UPDATE jobs SET status = 'running', attempts = attempts + 1, started_at = now()
		WHERE id = (
			SELECT id FROM jobs WHERE status = 'pending' AND run_at <= now()
			ORDER BY run_at FOR UPDATE SKIP LOCKED LIMIT 1)
		RETURNING id, kind, tenant_id, user_id, role, payload, attempts`).
		Scan(&j.id, &j.kind, &j.tenantID, &j.userID, &j.role, &j.payload, &j.attempts)
	if err == sql.ErrNoRows {
		return false
	}
	if err != nil {
		slog.Error("jobs: claim failed", "err", err)
		return false
	}
	h, ok := r.handlers[j.kind]
	if !ok {
		r.finish(ctx, j, fmt.Errorf("no handler for %q", j.kind), nil)
		return true
	}
	jctx := auth.WithPrincipal(ctx, auth.Principal{UserID: j.userID, TenantID: j.tenantID, Role: auth.Role(j.role)})
	jctx = WithJobID(jctx, j.id)
	r.finish(ctx, j, h(jctx, j.payload), ResultFrom(jctx))
	return true
}

func (r *Runner) finish(ctx context.Context, j job, runErr error, result json.RawMessage) {
	switch {
	case runErr == nil:
		_, _ = r.DB.ExecContext(ctx, `UPDATE jobs SET status = 'done', result = $2, finished_at = now() WHERE id = $1`, j.id, result)
	case j.attempts >= r.MaxAttempts:
		slog.Error("jobs: giving up", "id", j.id, "kind", j.kind, "err", runErr)
		_, _ = r.DB.ExecContext(ctx, `UPDATE jobs SET status = 'failed', last_error = $2, finished_at = now() WHERE id = $1`, j.id, runErr.Error())
	default:
		backoff := time.Duration(1<<j.attempts) * 10 * time.Second
		_, _ = r.DB.ExecContext(ctx, `UPDATE jobs SET status = 'pending', last_error = $2, run_at = now() + $3::interval WHERE id = $1`,
			j.id, runErr.Error(), fmt.Sprintf("%d seconds", int(backoff.Seconds())))
	}
}
