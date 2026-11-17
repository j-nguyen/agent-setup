package config

import "os"

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
