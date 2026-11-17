package jobs

import (
	"context"
	"encoding/json"
)

type jobIDKey struct{}
type resultKey struct{}

type resultBox struct{ v json.RawMessage }

// WithJobID marks ctx as running inside job id, with a slot for SetResult.
func WithJobID(ctx context.Context, id string) context.Context {
	ctx = context.WithValue(ctx, jobIDKey{}, id)
	return context.WithValue(ctx, resultKey{}, &resultBox{})
}

// SetResult stores a JSON result that Runner.Status returns to the client (e.g. a download URL).
func SetResult(ctx context.Context, v any) error {
	box, _ := ctx.Value(resultKey{}).(*resultBox)
	if box == nil {
		return nil
	}
	b, err := json.Marshal(v)
	box.v = b
	return err
}

func ResultFrom(ctx context.Context) json.RawMessage {
	if box, _ := ctx.Value(resultKey{}).(*resultBox); box != nil {
		return box.v
	}
	return nil
}
