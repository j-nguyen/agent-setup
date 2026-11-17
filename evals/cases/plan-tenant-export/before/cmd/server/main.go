package main

import (
	"context"
	"database/sql"
	"log"
	"net/http"
	"os"

	_ "github.com/lib/pq"

	"example.com/ledgerly/internal/audit"
	"example.com/ledgerly/internal/auth"
	"example.com/ledgerly/internal/invoices"
	"example.com/ledgerly/internal/jobs"
	"example.com/ledgerly/internal/notify"
	"example.com/ledgerly/internal/statements"
	"example.com/ledgerly/internal/storage"
)

func main() {
	db, err := sql.Open("postgres", os.Getenv("DATABASE_URL"))
	if err != nil {
		log.Fatal(err)
	}
	d := wire(db)

	runner := jobs.NewRunner(db)
	stmts := &statements.Service{Jobs: runner, Invoices: d.invoices, Storage: d.storage,
		Audit: d.audit, Notify: d.notify, Render: d.renderStatement}
	runner.Register(statements.JobKind, stmts.Generate)
	runner.Start(context.Background(), 4)

	inv := &invoices.Handlers{Repo: d.invoices}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/invoices", auth.RequireRole(auth.BillingRoles, inv.List))
	mux.HandleFunc("GET /api/invoices/{id}", auth.RequireRole(auth.BillingRoles, inv.Get))
	mux.HandleFunc("POST /api/statements", auth.RequireRole(auth.BillingRoles, stmts.Request))
	mux.HandleFunc("GET /api/statements/jobs/{id}", auth.RequireRole(auth.BillingRoles, stmts.JobStatus))

	log.Fatal(http.ListenAndServe(":8080", auth.Middleware(d.sessions, mux)))
}
