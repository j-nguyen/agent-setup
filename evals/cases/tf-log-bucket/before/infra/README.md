# acme-app infrastructure

`terraform -chdir=infra plan -var env=staging`. One state per environment.

Conventions:
- Least privilege: IAM statements name exact actions and exact resource ARNs.
- Data buckets keep S3 Block Public Access fully on and encrypt with KMS.
- Nothing that holds production data may be removable by a plain `terraform destroy`.
