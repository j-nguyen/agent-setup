package store

import (
	"context"
	"database/sql"
	"time"
)

type Order struct {
	ID         int64
	CustomerID int64
	TotalCents int64
	Status     string
	CreatedAt  time.Time
}

type Store struct{ DB *sql.DB }

const orderColumns = `id, customer_id, total_cents, status, created_at`

func (s *Store) OrderByID(ctx context.Context, id int64) (Order, error) {
	return scanOrder(s.DB.QueryRowContext(ctx,
		`SELECT `+orderColumns+` FROM orders WHERE id = $1`, id))
}

// OrdersAfter returns up to limit orders with id > afterID, in id order.
func (s *Store) OrdersAfter(ctx context.Context, afterID int64, limit int) ([]Order, error) {
	rows, err := s.DB.QueryContext(ctx,
		`SELECT `+orderColumns+` FROM orders WHERE id > $1 ORDER BY id LIMIT $2`, afterID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]Order, 0, limit)
	for rows.Next() {
		o, err := scanOrder(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, o)
	}
	return out, rows.Err()
}

type rowScanner interface {
	Scan(dest ...any) error
}

func scanOrder(r rowScanner) (Order, error) {
	var o Order
	err := r.Scan(&o.ID, &o.CustomerID, &o.TotalCents, &o.Status, &o.CreatedAt)
	return o, err
}
