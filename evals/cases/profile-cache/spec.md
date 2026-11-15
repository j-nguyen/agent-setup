Cache profile lookups in memory to cut load on the profiles database.

1. Cache `getProfile` results for 5 minutes, at most 10,000 entries (evict the oldest when full).
2. Profiles belong to a tenant. The same `userId` can exist in several tenants and they are different people.
3. Cache "not found" results for at most 30 seconds, so a newly created user shows up quickly.
4. Once `updateProfile` resolves, every later `getProfile` must return the updated profile, including when reads and updates for the same profile run concurrently.
5. Callers may modify the profile object they get back. That must not affect what other callers see.
6. Two concurrent cache misses for the same profile may both hit the database. That's acceptable.
