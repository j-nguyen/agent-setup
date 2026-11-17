package store

import (
	"context"
	"errors"
	"testing"
)

func TestCreateRejectsDuplicateEmail(t *testing.T) {
	s := NewMemoryStore()
	ctx := context.Background()
	if _, err := s.Create(ctx, User{Email: "ana@example.com", PasswordHash: "h"}); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Create(ctx, User{Email: "ANA@Example.com", PasswordHash: "h"}); !errors.Is(err, ErrDuplicateEmail) {
		t.Fatalf("err = %v, want ErrDuplicateEmail", err)
	}
}

func TestByEmailNotFound(t *testing.T) {
	if _, err := NewMemoryStore().ByEmail(context.Background(), "nobody@example.com"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
}

func TestCreateAssignsIDs(t *testing.T) {
	s := NewMemoryStore()
	ctx := context.Background()
	a, _ := s.Create(ctx, User{Email: "a@example.com"})
	b, _ := s.Create(ctx, User{Email: "b@example.com"})
	if a.ID == 0 || b.ID == a.ID {
		t.Fatalf("ids = %d, %d", a.ID, b.ID)
	}
}
