package main

import (
	"context"
	"database/sql"
	"errors"
	"io"
	"log/slog"
	"os"
	"time"

	"example.com/ledgerly/internal/auth"
	"example.com/ledgerly/internal/invoices"
	"example.com/ledgerly/internal/storage"
)

// The production S3 backend, mailer and PDF renderer live in the private
// ledgerly-infra module and are linked in by the release build. These defaults keep
// local development working without cloud credentials.

type devBackend struct{ dir string }

func newS3Backend() storage.Backend { return &devBackend{dir: os.TempDir()} }

func (b *devBackend) Upload(ctx context.Context, key, contentType string, r io.Reader) error {
	_, err := io.Copy(io.Discard, r)
	return err
}

func (b *devBackend) PresignGet(ctx context.Context, key string, ttl time.Duration, name string) (string, error) {
	return "http://localhost:8080/dev-files/" + key + "?expires=" + time.Now().Add(ttl).Format(time.RFC3339), nil
}

func (b *devBackend) SetExpiry(ctx context.Context, key string, ttl time.Duration) error { return nil }

type logMailer struct{}

func newMailer() logMailer { return logMailer{} }

func (logMailer) Send(ctx context.Context, userID, subject, body string) error {
	slog.Info("mail", "user", userID, "subject", subject)
	return nil
}

type dbSessions struct{ db *sql.DB }

func newSessionStore(db *sql.DB) auth.SessionStore { return dbSessions{db: db} }

func (s dbSessions) Lookup(ctx context.Context, token string) (auth.Principal, error) {
	var p auth.Principal
	var role string
	err := s.db.QueryRowContext(ctx,
		`SELECT user_id, tenant_id, role FROM sessions WHERE token = $1 AND expires_at > now()`, token).
		Scan(&p.UserID, &p.TenantID, &role)
	if errors.Is(err, sql.ErrNoRows) {
		return auth.Principal{}, errors.New("no session")
	}
	p.Role = auth.Role(role)
	return p, err
}

func renderStatementPDF(w io.Writer, month string, invs []invoices.Invoice) error {
	_, err := io.WriteString(w, "%PDF-1.4\n% dev statement "+month+"\n")
	return err
}
