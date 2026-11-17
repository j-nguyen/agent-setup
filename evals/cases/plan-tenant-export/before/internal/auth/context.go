// Package auth resolves the caller from the session and carries it in the context.
package auth

import (
	"context"
	"errors"
	"net/http"
	"slices"
)

type Role string

const (
	RoleOwner   Role = "owner"
	RoleAdmin   Role = "admin"
	RoleBilling Role = "billing"
	RoleMember  Role = "member"
)

// Principal is the authenticated caller. TenantID always comes from the session,
// never from the request.
type Principal struct {
	UserID   string
	TenantID string
	Role     Role
}

type ctxKey struct{}

var ErrNoPrincipal = errors.New("auth: no principal in context")

func WithPrincipal(ctx context.Context, p Principal) context.Context {
	return context.WithValue(ctx, ctxKey{}, p)
}

func FromContext(ctx context.Context) (Principal, error) {
	p, ok := ctx.Value(ctxKey{}).(Principal)
	if !ok || p.TenantID == "" {
		return Principal{}, ErrNoPrincipal
	}
	return p, nil
}

// SessionStore looks up a session cookie value.
type SessionStore interface {
	Lookup(ctx context.Context, token string) (Principal, error)
}

// Middleware authenticates every request and stores the Principal in the context.
func Middleware(sessions SessionStore, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		c, err := r.Cookie("session")
		if err != nil {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		p, err := sessions.Lookup(r.Context(), c.Value)
		if err != nil {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		next.ServeHTTP(w, r.WithContext(WithPrincipal(r.Context(), p)))
	})
}

// RequireRole allows the request only if the caller has one of the roles.
func RequireRole(roles []Role, next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		p, err := FromContext(r.Context())
		if err != nil {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		if !slices.Contains(roles, p.Role) {
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}
		next(w, r)
	}
}

// BillingRoles may see and manage invoices and payment data.
var BillingRoles = []Role{RoleOwner, RoleAdmin, RoleBilling}
