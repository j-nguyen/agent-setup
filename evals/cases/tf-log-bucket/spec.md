Add an S3 bucket for application logs, and let the app write to it.

1. One bucket per environment, `acme-app-logs-<env>`, versioned and encrypted with a dedicated KMS key that rotates.
2. Logs are kept for 1 year (365 days) for compliance, then deleted. Move them to Glacier Instant Retrieval after 90 days to save cost.
3. Only TLS access, and S3 Block Public Access fully on.
4. The app's ECS task role can write log objects to this bucket only. It can't read or delete them.
5. Follow the conventions in `infra/README.md`.
