Add `mergeContacts(contacts)` for the CSV import job, which dedupes contacts before they are saved.

1. Two contacts are duplicates when their emails match case-insensitively, ignoring surrounding whitespace.
2. A merged contact keeps the `name` and `createdAt` of the earliest-created record in the group.
3. `tags` is the union of all tags in the group, without duplicates.
4. Output emails are normalized (trimmed, lowercased).
5. Must not mutate the input array or the contact objects in it.
6. Imports can contain up to 200k contacts, so it must scale linearly.
7. Show the merged tags on the contact card, truncating long tags for display.
