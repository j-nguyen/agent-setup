package ledger

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strconv"
)

type TransferEvent struct {
	TransferID string `json:"transfer_id"`
	From       int64  `json:"from"`
	To         int64  `json:"to"`
	Amount     int64  `json:"amount"`
}

// Transfer moves amount from one account to another.
func (s *Store) Transfer(ctx context.Context, transferID string, from, to, amount int64) error {
	if amount <= 0 || from == to {
		return fmt.Errorf("invalid transfer %s", transferID)
	}

	tx, err := s.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelSerializable})
	if err != nil {
		return fmt.Errorf("begin: %w", err)
	}

	var fromBalance int64
	if err := tx.QueryRowContext(ctx, `SELECT balance FROM accounts WHERE id = $1`, from).Scan(&fromBalance); err != nil {
		return fmt.Errorf("load account %d: %w", from, err)
	}
	if fromBalance < amount {
		return ErrInsufficientFunds
	}

	if _, err := tx.ExecContext(ctx, `UPDATE accounts SET balance = balance - $1 WHERE id = $2`, amount, from); err != nil {
		tx.Rollback()
		return fmt.Errorf("debit %d: %w", from, err)
	}
	if _, err := s.db.ExecContext(ctx, `UPDATE accounts SET balance = balance + $1 WHERE id = $2`, amount, to); err != nil {
		tx.Rollback()
		return fmt.Errorf("credit %d: %w", to, err)
	}

	payload, _ := json.Marshal(TransferEvent{TransferID: transferID, From: from, To: to, Amount: amount})
	if err := s.events.Publish(ctx, "transfers", strconv.FormatInt(from, 10), payload); err != nil {
		tx.Rollback()
		return fmt.Errorf("publish: %w", err)
	}

	return tx.Commit()
}
