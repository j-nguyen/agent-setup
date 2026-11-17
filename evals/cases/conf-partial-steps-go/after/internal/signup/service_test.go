package signup

import (
	"context"
	"errors"
	"testing"
	"time"

	"example.com/accounts/internal/store"
)

type prefixHasher struct{}

func (prefixHasher) Hash(p string) (string, error) { return "hashed:" + p, nil }

func newTestService() *Service {
	s := NewService(store.NewMemoryStore(), prefixHasher{})
	s.Now = func() time.Time { return time.Date(2026, 11, 10, 9, 0, 0, 0, time.UTC) }
	return s
}

func TestRegisterNormalizesEmail(t *testing.T) {
	u, err := newTestService().Register(context.Background(), "  Ana@Example.COM ", "correct horse battery")
	if err != nil {
		t.Fatal(err)
	}
	if u.Email != "ana@example.com" {
		t.Fatalf("email = %q", u.Email)
	}
}

func TestRegisterRejectsInvalidEmail(t *testing.T) {
	for _, e := range []string{"", "not-an-email", "Ana <ana@example.com>"} {
		if _, err := newTestService().Register(context.Background(), e, "correct horse battery"); !errors.Is(err, ErrInvalidEmail) {
			t.Errorf("%q: err = %v, want ErrInvalidEmail", e, err)
		}
	}
}

func TestRegisterStoresHashNotPlaintext(t *testing.T) {
	u, err := newTestService().Register(context.Background(), "bo@example.com", "correct horse battery")
	if err != nil {
		t.Fatal(err)
	}
	if u.PasswordHash != "hashed:correct horse battery" {
		t.Fatalf("hash = %q", u.PasswordHash)
	}
}

func TestRegisterDuplicate(t *testing.T) {
	s := newTestService()
	ctx := context.Background()
	if _, err := s.Register(ctx, "cy@example.com", "correct horse battery"); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Register(ctx, "CY@example.com", "another long password"); !errors.Is(err, store.ErrDuplicateEmail) {
		t.Fatalf("err = %v, want ErrDuplicateEmail", err)
	}
}
