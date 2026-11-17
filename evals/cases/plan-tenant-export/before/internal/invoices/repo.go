package invoices

import (
	"context"
	"database/sql"
	"errors"
	"time"

	"example.com/ledgerly/internal/auth"
)

var ErrNotFound = errors.New("invoice not found")

// MaxPageSize caps a single page read, for the API and for batch readers.
const MaxPageSize = 500

type Repo struct {
	DB *sql.DB
}

// Filter narrows a listing. The tenant is never part of it: it always comes from ctx.
type Filter struct {
	Status   Status
	IssuedGE time.Time
	IssuedLT time.Time
}

const cols = `id, tenant_id, number, customer_name, customer_ref, currency, total_cents, status, issued_at, due_at, memo`

func scan(row interface{ Scan(...any) error }) (Invoice, error) {
	var inv Invoice
	err := row.Scan(&inv.ID, &inv.TenantID, &inv.Number, &inv.CustomerName, &inv.CustomerRef,
		&inv.Currency, &inv.TotalCents, &inv.Status, &inv.IssuedAt, &inv.DueAt, &inv.Memo)
	return inv, err
}

func (r *Repo) Get(ctx context.Context, id string) (Invoice, error) {
	p, err := auth.FromContext(ctx)
	if err != nil {
		return Invoice{}, err
	}
	inv, err := scan(r.DB.QueryRowContext(ctx,
		`SELECT `+cols+` FROM invoices WHERE tenant_id = $1 AND id = $2`, p.TenantID, id))
	if errors.Is(err, sql.ErrNoRows) {
		return Invoice{}, ErrNotFound
	}
	return inv, err
}

// ListPage returns up to limit invoices after the cursor (keyset pagination on
// (issued_at, id)), newest first. Pass the last row's Cursor to get the next page.
// Uses the invoices_tenant_issued index.
func (r *Repo) ListPage(ctx context.Context, f Filter, after Cursor, limit int) ([]Invoice, error) {
	p, err := auth.FromContext(ctx)
	if err != nil {
		return nil, err
	}
	if limit <= 0 || limit > MaxPageSize {
		limit = MaxPageSize
	}
	q := `SELECT ` + cols + ` FROM invoices
	      WHERE tenant_id = $1
	        AND ($2 = '' OR status = $2)
	        AND ($3::timestamptz IS NULL OR issued_at >= $3)
	        AND ($4::timestamptz IS NULL OR issued_at < $4)
	        AND ($5::timestamptz IS NULL OR (issued_at, id) < ($5, $6))
	      ORDER BY issued_at DESC, id DESC
	      LIMIT $7`
	rows, err := r.DB.QueryContext(ctx, q, p.TenantID, string(f.Status),
		nullTime(f.IssuedGE), nullTime(f.IssuedLT), nullTime(after.IssuedAt), nullString(after.ID), limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Invoice
	for rows.Next() {
		inv, err := scan(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, inv)
	}
	return out, rows.Err()
}

// Cursor is the keyset position after a row.
type Cursor struct {
	IssuedAt time.Time
	ID       string
}

func CursorOf(inv Invoice) Cursor { return Cursor{IssuedAt: inv.IssuedAt, ID: inv.ID} }

func nullString(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func nullTime(t time.Time) any {
	if t.IsZero() {
		return nil
	}
	return t
}
