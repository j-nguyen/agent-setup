// Package audit records who did what to billing data. Entries are append-only and
// visible to tenant admins under Settings → Audit log.
package audit

import (
	"context"
	"database/sql"
	"encoding/json"

	"example.com/ledgerly/internal/auth"
)

type Log struct {
	DB *sql.DB
}

// Record appends an entry for the caller. details must not contain secrets or full card data.
func (l *Log) Record(ctx context.Context, action, target string, details map[string]any) error {
	p, err := auth.FromContext(ctx)
	if err != nil {
		return err
	}
	b, err := json.Marshal(details)
	if err != nil {
		return err
	}
	_, err = l.DB.ExecContext(ctx,
		`INSERT INTO audit_log (tenant_id, user_id, action, target, details) VALUES ($1, $2, $3, $4, $5)`,
		p.TenantID, p.UserID, action, target, b)
	return err
}
