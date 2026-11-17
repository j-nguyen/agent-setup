// Package httpapi is the HTTP layer. It translates requests into calls on
// domain services and never touches storage directly.
package httpapi

import (
	"encoding/json"
	"net/http"
)

type Server struct {
	mux *http.ServeMux
}

func NewServer() *Server {
	s := &Server{mux: http.NewServeMux()}
	s.mux.HandleFunc("GET /healthz", s.health)
	return s
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.mux.ServeHTTP(w, r)
}

func (s *Server) health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
