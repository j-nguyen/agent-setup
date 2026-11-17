package export

import (
	"bytes"
	"context"
	"encoding/csv"
	"errors"
	"os"
	"sort"
	"strconv"
	"testing"
	"time"

	"example.com/ledger/internal/store"
)

type fakePager struct {
	orders []store.Order // sorted by ID
	calls  int
	err    error
}

func (f *fakePager) OrdersAfter(_ context.Context, afterID int64, limit int) ([]store.Order, error) {
	f.calls++
	if f.err != nil {
		return nil, f.err
	}
	i := sort.Search(len(f.orders), func(i int) bool { return f.orders[i].ID > afterID })
	j := i + limit
	if j > len(f.orders) {
		j = len(f.orders)
	}
	return f.orders[i:j], nil
}

func makeOrders(n int) []store.Order {
	loc := time.FixedZone("CET", 3600)
	out := make([]store.Order, n)
	for i := range out {
		out[i] = store.Order{
			ID:         int64(i*2 + 1), // gaps in ids, like a real table after deletes
			CustomerID: 7,
			TotalCents: 1999,
			Status:     "paid",
			CreatedAt:  time.Date(2026, 11, 3, 1, 0, 0, 0, loc),
		}
	}
	return out
}

func TestWriteAllBatchesInOrder(t *testing.T) {
	src := &fakePager{orders: makeOrders(2500)}
	var buf bytes.Buffer
	n, err := Write(context.Background(), src, &buf)
	if err != nil {
		t.Fatal(err)
	}
	if n != 2500 || src.calls != 3 {
		t.Fatalf("got %d rows in %d calls, want 2500 in 3", n, src.calls)
	}
	recs, err := csv.NewReader(&buf).ReadAll()
	if err != nil {
		t.Fatal(err)
	}
	if got := len(recs); got != 2501 {
		t.Fatalf("got %d records, want header + 2500", got)
	}
	prev := int64(0)
	for _, r := range recs[1:] {
		id, _ := strconv.ParseInt(r[0], 10, 64)
		if id <= prev {
			t.Fatalf("ids out of order: %d after %d", id, prev)
		}
		prev = id
	}
}

func TestFormatting(t *testing.T) {
	var buf bytes.Buffer
	if _, err := Write(context.Background(), &fakePager{orders: makeOrders(1)}, &buf); err != nil {
		t.Fatal(err)
	}
	want := "id,customer_id,total_cents,status,created_at\n1,7,1999,paid,2026-11-03T00:00:00Z\n"
	if buf.String() != want {
		t.Fatalf("got %q, want %q", buf.String(), want)
	}
}

func TestErrorLeavesNoFile(t *testing.T) {
	dir := t.TempDir()
	_, _, err := ToFile(context.Background(), &fakePager{err: errors.New("db down")}, dir, time.Now())
	if err == nil {
		t.Fatal("want an error")
	}
	entries, _ := os.ReadDir(dir)
	if len(entries) != 0 {
		t.Fatalf("export dir not empty after failure: %v", entries)
	}
}
