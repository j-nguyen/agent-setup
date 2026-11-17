// Package export writes the nightly orders CSV for finance.
package export

import (
	"context"
	"encoding/csv"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"example.com/ledger/internal/config"
	"example.com/ledger/internal/store"
)

// OrderPager returns up to limit orders with id > afterID, in id order.
type OrderPager interface {
	OrdersAfter(ctx context.Context, afterID int64, limit int) ([]store.Order, error)
}

var header = []string{"id", "customer_id", "total_cents", "status", "created_at"}

// Write streams every order as CSV, lowest id first, and returns the number of rows written.
func Write(ctx context.Context, src OrderPager, w io.Writer) (int, error) {
	cw := csv.NewWriter(w)
	if err := cw.Write(header); err != nil {
		return 0, err
	}
	n := 0
	var lastID int64
	for {
		batch, err := src.OrdersAfter(ctx, lastID, config.ExportBatchSize)
		if err != nil {
			return n, fmt.Errorf("export: read orders after id %d: %w", lastID, err)
		}
		for _, o := range batch {
			rec := []string{
				strconv.FormatInt(o.ID, 10),
				strconv.FormatInt(o.CustomerID, 10),
				strconv.FormatInt(o.TotalCents, 10),
				o.Status,
				o.CreatedAt.UTC().Format(time.RFC3339),
			}
			if err := cw.Write(rec); err != nil {
				return n, err
			}
			n++
		}
		if len(batch) < config.ExportBatchSize {
			break
		}
		lastID = batch[len(batch)-1].ID
	}
	cw.Flush()
	return n, cw.Error()
}

// ToFile writes the export for day into dir through a temp file and a rename, so readers
// never see a partial file. It returns the final path and the number of rows.
func ToFile(ctx context.Context, src OrderPager, dir string, day time.Time) (string, int, error) {
	final := filepath.Join(dir, "orders-"+day.UTC().Format("2006-01-02")+".csv")
	tmp, err := os.CreateTemp(dir, ".orders-*.csv.tmp")
	if err != nil {
		return "", 0, err
	}
	defer os.Remove(tmp.Name()) // no-op once the rename has happened
	n, err := Write(ctx, src, tmp)
	if err != nil {
		tmp.Close()
		return "", n, err
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return "", n, err
	}
	if err := tmp.Close(); err != nil {
		return "", n, err
	}
	if err := os.Rename(tmp.Name(), final); err != nil {
		return "", n, err
	}
	return final, n, nil
}
