// Package ledger stores wallet balances in Postgres.
//
//	CREATE TABLE accounts (
//	  id      bigint PRIMARY KEY,
//	  balance bigint NOT NULL CHECK (balance >= 0)
//	);
package ledger

import (
	"context"
	"database/sql"
	"errors"

	"example.com/wallet/internal/events"
)

var ErrInsufficientFunds = errors.New("insufficient funds")

type Store struct {
	db     *sql.DB // pgx stdlib driver; pool of 20 connections
	events events.Publisher
}

func NewStore(db *sql.DB, pub events.Publisher) *Store {
	return &Store{db: db, events: pub}
}

func (s *Store) Balance(ctx context.Context, accountID int64) (int64, error) {
	var b int64
	err := s.db.QueryRowContext(ctx, `SELECT balance FROM accounts WHERE id = $1`, accountID).Scan(&b)
	return b, err
}
