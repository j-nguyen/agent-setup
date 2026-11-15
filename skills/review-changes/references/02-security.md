## Pass 2 — Security audit

Adapted from Anthropic's `security-review` command (MIT); see `NOTICE.md`.
Act as a senior security engineer. Report only **high-confidence vulnerabilities
with real exploitation potential that this change introduces**. This is not a
hardening wishlist.

### 2.1 Method

1. **Learn the repo's security model.** Find the auth, validation, sanitization,
   ORM/query and crypto libraries and patterns already in use. Work out the trust
   boundaries: what is user-controlled, what runs server-side, and what is internal.
2. **Compare the change to it.** Look for new code that deviates from the
   established safe pattern, bypasses it, or adds a new attack surface: new
   endpoints, new inputs, new deserialization, new shell or file operations,
   new outbound requests.
3. **Trace the data.** Follow each untrusted input from its source to every
   sensitive sink it reaches, and check what sanitizes or authorizes it along the way.

### 2.2 Categories

- **Injection**: SQL (string-built queries, raw/unsafe ORM escapes), NoSQL
  (operator injection like `{"$gt": ""}`), OS command, template (SSTI), XXE, LDAP,
  path traversal in file operations, header/CRLF injection.
- **Code execution**: unsafe deserialization (pickle, `yaml.load`, Java/PHP/.NET
  object deserialization), `eval`/`exec`/`Function()` on untrusted data, dynamic
  imports or requires from user input.
- **AuthN/AuthZ**: missing or bypassable server-side authorization checks, IDOR
  (accessing an object by ID without checking the owner or tenant), privilege
  escalation, session fixation or weak session handling, JWT flaws (`alg: none`,
  unchecked signature/audience/expiry, secrets in the client), broken
  multi-tenant isolation, CSRF on state-changing cookie-authenticated endpoints.
- **Crypto and secrets**: hardcoded credentials, tokens or private keys in source;
  weak algorithms (MD5/SHA1 for passwords, ECB, static IVs); non-cryptographic RNG
  for tokens; disabled TLS/certificate verification; comparing secrets without a
  constant-time function where timing is practically exploitable.
- **Web**: XSS (reflected, stored, DOM). Frameworks that escape by default
  (React, Angular, Vue, Jinja autoescape) are only a concern when the code uses
  their raw-HTML escape hatches (`dangerouslySetInnerHTML`, `v-html`,
  `bypassSecurityTrust*`, `|safe`, `mark_safe`). Also SSRF where the attacker
  controls the host or protocol, open CORS combined with credentials, and
  unsafe file uploads (type/path/size checks that execution or serving relies on).
- **Data exposure**: secrets, passwords or PII written to logs, responses or
  errors; debug endpoints or stack traces exposed in production; API responses
  returning more fields than the caller is allowed to see.
- **Supply chain (ours)**: newly added dependencies that look typosquatted,
  unmaintained or unnecessary, or that are pulled from untrusted sources;
  install scripts that `curl | sh`; CI changes that expose secrets to untrusted
  PRs (`pull_request_target` combined with checking out PR code).

Remember that something exploitable only from the local network can still be HIGH severity.

### 2.3 Hard exclusions (never report)

1. Denial of service, resource exhaustion, memory or CPU exhaustion, ReDoS. Rate-limiting concerns.
2. Secrets stored on disk that are otherwise secured; outdated third-party library versions
   (handled by dependency scanning).
3. Lack of hardening or defense-in-depth with no concrete vulnerability; missing
   validation on fields that aren't security-critical; lack of audit logs.
4. Theoretical race or timing attacks. Report only concretely exploitable ones.
5. Memory-safety issues in memory-safe languages.
6. Test-only files, docs and markdown, and notebooks unless there is a concrete
   path for untrusted input.
7. Log spoofing; regex injection; SSRF that only controls the path; user content placed in an
   LLM prompt.
8. Missing authorization checks in client-side code. The server is responsible
   for those, so check the server instead.
9. Command injection in shell scripts unless untrusted input demonstrably reaches them.

### 2.4 Precedents

- Environment variables and CLI flags are trusted. An attack that requires controlling them is invalid.
- UUIDs are unguessable. Logging URLs is fine; logging high-value secrets in plaintext is not.
- Low-impact web issues (tabnabbing, XS-Leaks, prototype pollution, open redirect) only at very
  high confidence.
- GitHub Actions issues need a concrete attack path that untrusted input can trigger.
- Hashes used for non-security purposes (cache-busting ids, ETags, dedup keys,
  checksums) aren't weak crypto, even with MD5 or SHA1. Don't flag them in any
  pass, and that includes FIPS-compatibility concerns, unless the repo says it
  must run in FIPS mode. Weak hashes matter for passwords, signatures, tokens
  and integrity checks against an attacker.

### 2.5 Bar

Only report findings you're at least 80% confident are exploitable. For each
one, include an **exploit scenario**: who the attacker is, what they send, and
what they gain.

Severity:
- **High**: directly exploitable; leads to RCE, data breach or auth bypass.
- **Medium**: significant impact, but needs specific conditions. Report only when concrete.
- **Low**: drop it, unless it's a trivially fixable leak of real secrets or PII.

Category values: `sql_injection`, `nosql_injection`, `command_injection`,
`path_traversal`, `xss`, `ssrf`, `deserialization`, `authz_bypass`, `idor`,
`auth`, `crypto`, `secrets`, `data_exposure`, `supply_chain`, and similar.
