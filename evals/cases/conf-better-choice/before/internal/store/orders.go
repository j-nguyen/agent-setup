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

func (s *Store) OrderByID(ctx context.Context, id int64) (Order, error) {
	var o Order
	err := s.DB.QueryRowContext(ctx,
		`SELECT id, customer_id, total_cents, status, created_at FROM orders WHERE id = $1`, id).
		Scan(&o.ID, &o.CustomerID, &o.TotalCents, &o.Status, &o.CreatedAt)
	return o, err
}
