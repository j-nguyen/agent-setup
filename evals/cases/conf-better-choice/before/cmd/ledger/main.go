package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"os"
	"strconv"

	_ "github.com/jackc/pgx/v5/stdlib"

	"example.com/ledger/internal/config"
	"example.com/ledger/internal/store"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: ledger show ORDER_ID")
		os.Exit(2)
	}
	cfg := config.FromEnv()
	db, err := sql.Open("pgx", cfg.DatabaseURL)
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	s := &store.Store{DB: db}
	ctx := context.Background()

	switch os.Args[1] {
	case "show":
		id, err := strconv.ParseInt(os.Args[2], 10, 64)
		if err != nil {
			log.Fatalf("bad order id %q", os.Args[2])
		}
		o, err := s.OrderByID(ctx, id)
		if err != nil {
			log.Fatal(err)
		}
		fmt.Printf("%d\t%d\t%d\t%s\t%s\n", o.ID, o.CustomerID, o.TotalCents, o.Status, o.CreatedAt.Format("2006-01-02"))
	default:
		fmt.Fprintf(os.Stderr, "unknown command %q\n", os.Args[1])
		os.Exit(2)
	}
}
