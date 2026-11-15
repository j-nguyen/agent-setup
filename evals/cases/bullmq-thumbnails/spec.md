Generate thumbnails in the background with BullMQ.

1. After an upload is stored, queue a job that writes 128px and 512px WebP thumbnails. The worker runs as its own process (`worker` in the Procfile).
2. Clients retry `PUT /uploads/:uploadId` with the same `uploadId` on timeouts. Each upload gets one thumbnail job, not one per retry.
3. Thumbnail jobs can fail transiently (S3 or sharp errors). Retry them up to 5 times with exponential backoff starting at 10 seconds.
4. Don't let finished jobs accumulate in Redis. Keep the last 1,000 completed jobs, and failed jobs for 7 days.
5. Deploys send the worker SIGTERM and kill it 30 seconds later. Jobs in progress must be allowed to finish, and no new ones started.
6. The worker must keep working through short Redis outages.
