// Package storage stores generated files in the object store and hands out
// short-lived signed download URLs. Keys are always prefixed with the tenant.
package storage

import (
	"context"
	"fmt"
	"io"
	"time"

	"example.com/ledgerly/internal/auth"
)

// MaxURLTTL is the longest a signed URL may live.
const MaxURLTTL = 24 * time.Hour

// Backend is implemented by the S3-compatible client in prod and by an in-memory fake in tests.
type Backend interface {
	// Upload streams r to key. It must not buffer the whole object in memory.
	Upload(ctx context.Context, key, contentType string, r io.Reader) error
	PresignGet(ctx context.Context, key string, ttl time.Duration, downloadName string) (string, error)
	// SetExpiry deletes the object automatically after ttl (lifecycle rule).
	SetExpiry(ctx context.Context, key string, ttl time.Duration) error
}

type Client struct {
	Backend Backend
}

// TenantKey builds the object key for a file owned by the caller's tenant.
func TenantKey(ctx context.Context, parts ...string) (string, error) {
	p, err := auth.FromContext(ctx)
	if err != nil {
		return "", err
	}
	key := "tenants/" + p.TenantID
	for _, s := range parts {
		key += "/" + s
	}
	return key, nil
}

// PutTenantFile streams a file into the caller's tenant prefix and sets it to expire after retain.
func (c *Client) PutTenantFile(ctx context.Context, name, contentType string, r io.Reader, retain time.Duration) (string, error) {
	key, err := TenantKey(ctx, name)
	if err != nil {
		return "", err
	}
	if err := c.Backend.Upload(ctx, key, contentType, r); err != nil {
		return "", fmt.Errorf("storage: upload %s: %w", key, err)
	}
	if retain > 0 {
		if err := c.Backend.SetExpiry(ctx, key, retain); err != nil {
			return "", err
		}
	}
	return key, nil
}

// SignedURL returns a download URL for a key in the caller's tenant prefix.
func (c *Client) SignedURL(ctx context.Context, key string, ttl time.Duration, downloadName string) (string, error) {
	prefix, err := TenantKey(ctx)
	if err != nil {
		return "", err
	}
	if len(key) <= len(prefix) || key[:len(prefix)+1] != prefix+"/" {
		return "", fmt.Errorf("storage: key %q outside tenant prefix", key)
	}
	if ttl <= 0 || ttl > MaxURLTTL {
		ttl = MaxURLTTL
	}
	return c.Backend.PresignGet(ctx, key, ttl, downloadName)
}
