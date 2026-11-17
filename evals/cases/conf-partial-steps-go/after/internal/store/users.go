// Package store holds user persistence. MemoryStore is the only implementation for now.
package store

import (
	"context"
	"errors"
	"strings"
	"sync"
	"time"
)

var (
	ErrDuplicateEmail = errors.New("store: email already registered")
	ErrNotFound       = errors.New("store: user not found")
)

type User struct {
	ID           int64
	Email        string
	PasswordHash string
	CreatedAt    time.Time
}

type UserStore interface {
	Create(ctx context.Context, u User) (User, error)
	ByEmail(ctx context.Context, email string) (User, error)
}

// MemoryStore is a concurrency-safe in-memory UserStore.
type MemoryStore struct {
	mu      sync.Mutex
	nextID  int64
	byID    map[int64]User
	byEmail map[string]int64
}

func NewMemoryStore() *MemoryStore {
	return &MemoryStore{byID: map[int64]User{}, byEmail: map[string]int64{}}
}

func emailKey(email string) string {
	return strings.ToLower(strings.TrimSpace(email))
}

func (s *MemoryStore) Create(_ context.Context, u User) (User, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	key := emailKey(u.Email)
	if _, taken := s.byEmail[key]; taken {
		return User{}, ErrDuplicateEmail
	}
	s.nextID++
	u.ID = s.nextID
	s.byID[u.ID] = u
	s.byEmail[key] = u.ID
	return u, nil
}

func (s *MemoryStore) ByEmail(_ context.Context, email string) (User, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	id, ok := s.byEmail[emailKey(email)]
	if !ok {
		return User{}, ErrNotFound
	}
	return s.byID[id], nil
}
