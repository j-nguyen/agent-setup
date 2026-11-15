Send weekly activity digests and welcome emails from Sidekiq (Sidekiq 8).

1. New users get a welcome email from a background job. The job must never run before the user row is committed.
2. Every Monday, the scheduler runs `EnqueueWeeklyDigestsJob`, which queues one `SendDigestJob` per opted-in user. There are about 2 million users, so don't load them all at once or push them to Redis one at a time.
3. Each user gets one digest per week, even when a job is enqueued twice or two jobs run at once. Don't lose a digest because of a transient failure: retry it. When a send fails ambiguously (an SMTP timeout after the server may have accepted it, a worker shutdown or kill mid-send), a rare duplicate is acceptable; product prefers that to a missed digest. If a worker process is killed outright (OOM, SIGKILL), losing that user's digest for the week is acceptable. SMTP delivery is configured with 10-second open and read timeouts.
4. Users who opt out after the fan-out don't get that week's digest.
5. Emails go through a `mailers` queue, which our Sidekiq processes must actually work.
