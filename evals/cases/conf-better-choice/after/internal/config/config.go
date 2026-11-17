package config

import "os"

// ExportBatchSize is how many orders the nightly export reads per query.
const ExportBatchSize = 1000

// Config is read once at startup from the environment.
type Config struct {
	DatabaseURL string
	ExportDir   string
}

func FromEnv() Config {
	dir := os.Getenv("LEDGER_EXPORT_DIR")
	if dir == "" {
		dir = "/var/lib/ledger/exports"
	}
	return Config{DatabaseURL: os.Getenv("DATABASE_URL"), ExportDir: dir}
}
