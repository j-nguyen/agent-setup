package main

import (
	"database/sql"
	"io"

	"example.com/ledgerly/internal/audit"
	"example.com/ledgerly/internal/auth"
	"example.com/ledgerly/internal/invoices"
	"example.com/ledgerly/internal/notify"
	"example.com/ledgerly/internal/storage"
)

type deps struct {
	invoices        *invoices.Repo
	storage         *storage.Client
	audit           *audit.Log
	notify          *notify.Notifier
	sessions        auth.SessionStore
	renderStatement func(io.Writer, string, []invoices.Invoice) error
}

// wire builds the production dependencies. The S3 backend, session store, mailer and
// PDF renderer are constructed from environment configuration in config.go.
func wire(db *sql.DB) deps {
	return deps{
		invoices:        &invoices.Repo{DB: db},
		storage:         &storage.Client{Backend: newS3Backend()},
		audit:           &audit.Log{DB: db},
		notify:          &notify.Notifier{DB: db, Mailer: newMailer()},
		sessions:        newSessionStore(db),
		renderStatement: renderStatementPDF,
	}
}
