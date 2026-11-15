// Package events publishes domain events to Kafka.
package events

import "context"

// Publisher sends a message to a Kafka topic. Publish blocks until the broker
// acknowledges the write (typically 5-50 ms, seconds when the cluster is degraded).
type Publisher interface {
	Publish(ctx context.Context, topic string, key string, value []byte) error
}
