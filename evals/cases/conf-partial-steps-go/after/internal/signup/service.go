// Package signup owns the rules for creating accounts.
package signup

import (
	"context"
	"errors"
	"fmt"
	"net/mail"
	"strings"
	"time"

	"example.com/accounts/internal/store"
)

var (
	ErrInvalidEmail = errors.New("signup: invalid email address")
	ErrWeakPassword = errors.New("signup: password must be at least 12 characters")
)

// MinPasswordLen is the minimum password length in characters.
const MinPasswordLen = 12

// Hasher turns a plaintext password into a storable hash (bcrypt in production).
type Hasher interface {
	Hash(password string) (string, error)
}

type Service struct {
	Store  store.UserStore
	Hasher Hasher
	Now    func() time.Time
}

func NewService(s store.UserStore, h Hasher) *Service {
	return &Service{Store: s, Hasher: h, Now: time.Now}
}

// Register validates the input and creates the user.
func (s *Service) Register(ctx context.Context, email, password string) (store.User, error) {
	email = strings.ToLower(strings.TrimSpace(email))
	addr, err := mail.ParseAddress(email)
	if err != nil || addr.Address != email {
		return store.User{}, ErrInvalidEmail
	}
	hash, err := s.Hasher.Hash(password)
	if err != nil {
		return store.User{}, fmt.Errorf("signup: hashing password: %w", err)
	}
	return s.Store.Create(ctx, store.User{
		Email:        email,
		PasswordHash: hash,
		CreatedAt:    s.Now().UTC(),
	})
}
