package invoices

import (
	"errors"
	"net/http"
	"strconv"
	"time"

	"example.com/ledgerly/internal/httpx"
)

type Handlers struct {
	Repo *Repo
}

// GET /api/invoices?status=open&limit=50&after_issued=...&after_id=...
func (h *Handlers) List(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	limit, _ := strconv.Atoi(q.Get("limit"))
	if limit <= 0 || limit > 100 {
		limit = 50
	}
	var after Cursor
	if s := q.Get("after_issued"); s != "" {
		t, err := time.Parse(time.RFC3339Nano, s)
		if err != nil {
			httpx.Error(w, http.StatusBadRequest, "bad after_issued")
			return
		}
		after = Cursor{IssuedAt: t, ID: q.Get("after_id")}
	}
	items, err := h.Repo.ListPage(r.Context(), Filter{Status: Status(q.Get("status"))}, after, limit)
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "could not list invoices")
		return
	}
	httpx.JSON(w, http.StatusOK, map[string]any{"items": items})
}

// GET /api/invoices/{id}
func (h *Handlers) Get(w http.ResponseWriter, r *http.Request) {
	inv, err := h.Repo.Get(r.Context(), r.PathValue("id"))
	if errors.Is(err, ErrNotFound) {
		httpx.Error(w, http.StatusNotFound, "not found")
		return
	}
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "could not load invoice")
		return
	}
	httpx.JSON(w, http.StatusOK, inv)
}
