// Package statements generates monthly account statements (PDF) in the background.
// It's the reference implementation for "generate a file for the customer" features:
// enqueue → job reads in pages → stream to storage → audit → notify → signed URL on demand.
package statements

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"example.com/ledgerly/internal/audit"
	"example.com/ledgerly/internal/auth"
	"example.com/ledgerly/internal/httpx"
	"example.com/ledgerly/internal/invoices"
	"example.com/ledgerly/internal/jobs"
	"example.com/ledgerly/internal/notify"
	"example.com/ledgerly/internal/storage"
)

const JobKind = "statements.generate"

// Retain generated statements for 7 days; links are valid for 15 minutes.
const (
	retain = 7 * 24 * time.Hour
	urlTTL = 15 * time.Minute
)

type Service struct {
	Jobs     *jobs.Runner
	Invoices *invoices.Repo
	Storage  *storage.Client
	Audit    *audit.Log
	Notify   *notify.Notifier
	Render   func(w io.Writer, month string, invs []invoices.Invoice) error
}

type payload struct {
	Month string `json:"month"` // "2026-10"
}

type result struct {
	Key string `json:"key"`
}

// POST /api/statements {month} -> 202 {job_id}
func (s *Service) Request(w http.ResponseWriter, r *http.Request) {
	var p payload
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil || len(p.Month) != 7 {
		httpx.Error(w, http.StatusBadRequest, "month must be YYYY-MM")
		return
	}
	id, err := s.Jobs.Enqueue(r.Context(), JobKind, "statement:"+p.Month, p)
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "could not start")
		return
	}
	_ = s.Audit.Record(r.Context(), "statement.requested", p.Month, nil)
	httpx.JSON(w, http.StatusAccepted, map[string]string{"job_id": id})
}

// GET /api/statements/jobs/{id} -> 200 {status, url?}
func (s *Service) JobStatus(w http.ResponseWriter, r *http.Request) {
	status, raw, err := s.Jobs.Status(r.Context(), r.PathValue("id"))
	if err != nil {
		httpx.Error(w, http.StatusNotFound, "not found")
		return
	}
	resp := map[string]string{"status": status}
	var res result
	if status == "done" && json.Unmarshal(raw, &res) == nil && res.Key != "" {
		url, err := s.Storage.SignedURL(r.Context(), res.Key, urlTTL, "statement.pdf")
		if err != nil {
			httpx.Error(w, http.StatusInternalServerError, "could not sign url")
			return
		}
		resp["url"] = url
	}
	httpx.JSON(w, http.StatusOK, resp)
}

// Generate is the job handler. It runs with the requesting user's Principal in ctx.
func (s *Service) Generate(ctx context.Context, raw json.RawMessage) error {
	var p payload
	if err := json.Unmarshal(raw, &p); err != nil {
		return err
	}
	start, err := time.Parse("2006-01", p.Month)
	if err != nil {
		return err
	}
	filter := invoices.Filter{IssuedGE: start, IssuedLT: start.AddDate(0, 1, 0)}
	var all []invoices.Invoice
	var after invoices.Cursor
	for { // statements are small (one month), so collecting them is fine here
		page, err := s.Invoices.ListPage(ctx, filter, after, invoices.MaxPageSize)
		if err != nil {
			return err
		}
		all = append(all, page...)
		if len(page) < invoices.MaxPageSize {
			break
		}
		after = invoices.CursorOf(page[len(page)-1])
	}
	pr, pw := io.Pipe()
	go func() { pw.CloseWithError(s.Render(pw, p.Month, all)) }()
	key, err := s.Storage.PutTenantFile(ctx, fmt.Sprintf("statements/%s-%d.pdf", p.Month, time.Now().Unix()),
		"application/pdf", pr, retain)
	if err != nil {
		return err
	}
	principal, _ := auth.FromContext(ctx)
	_ = s.Audit.Record(ctx, "statement.generated", p.Month, map[string]any{"invoices": len(all)})
	if err := s.Notify.Ready(ctx, principal.TenantID, principal.UserID,
		"Your "+p.Month+" statement is ready", "/billing/statements"); err != nil {
		return err
	}
	return jobs.SetResult(ctx, result{Key: key})
}
