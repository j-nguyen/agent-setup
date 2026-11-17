// Package notify tells a user that something they started has finished:
// an in-app notification plus an email.
package notify

import (
	"context"
	"database/sql"
)

type Mailer interface {
	Send(ctx context.Context, userID, subject, body string) error
}

type Notifier struct {
	DB     *sql.DB
	Mailer Mailer
}

// Ready tells userID that a file is ready, linking to a dashboard page (not the file itself:
// the page asks for a fresh signed URL, so emails never carry long-lived links).
func (n *Notifier) Ready(ctx context.Context, tenantID, userID, title, dashboardPath string) error {
	if _, err := n.DB.ExecContext(ctx,
		`INSERT INTO notifications (tenant_id, user_id, title, link) VALUES ($1, $2, $3, $4)`,
		tenantID, userID, title, dashboardPath); err != nil {
		return err
	}
	return n.Mailer.Send(ctx, userID, title, "Open "+dashboardPath+" to download it.")
}
