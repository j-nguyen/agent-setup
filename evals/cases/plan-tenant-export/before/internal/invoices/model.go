package invoices

import "time"

type Status string

const (
	StatusDraft Status = "draft"
	StatusOpen  Status = "open"
	StatusPaid  Status = "paid"
	StatusVoid  Status = "void"
)

type Invoice struct {
	ID           string
	TenantID     string
	Number       string
	CustomerName string
	CustomerRef  string
	Currency     string
	TotalCents   int64
	Status       Status
	IssuedAt     time.Time
	DueAt        time.Time
	Memo         string
}
