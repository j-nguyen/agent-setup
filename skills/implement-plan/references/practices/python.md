# Python

Check the project's Python version (`pyproject.toml`, `.python-version`) and
use only syntax and stdlib features it supports.

**Types and structure**
- Type-annotate new and changed function signatures. Use built-in generics
  (`list[str]`, `dict[str, int]`, `X | None`) when the version allows.
- `@dataclass` (or the repo's Pydantic/attrs models) for structured data, not
  loose dicts passed between functions. `frozen=True` when it shouldn't change.
- `Enum` / `Literal` for a fixed set of values, not bare strings.
- Small functions with one job; early returns. Module-level code does no work
  at import time beyond definitions and constants.
- Don't add `Protocol`/`ABC` hierarchies, registries or factory classes unless
  there are several real implementations today. A plain function is fine.
- Reuse the repo's helpers (serialization, config, logging) instead of
  re-implementing them.

**Correctness**
- No mutable default arguments (`def f(x=[])`). Use `None` and create inside.
- `is None` / `is not None`, not `== None`. Don't rely on truthiness when `0`
  or `""` is a valid value.
- Don't mutate a list or dict you were passed unless that's the function's job.
- `with` for files, locks, connections and transactions.
- Use `pathlib` for paths. Open text files with an explicit `encoding="utf-8"`.
- Timezone-aware datetimes (`datetime.now(UTC)`), never naive `utcnow()`.
- `decimal.Decimal` (or integer minor units) for money, never `float`.

**Errors**
- Catch specific exceptions, never bare `except:` or a blanket
  `except Exception: pass`. Re-raise with context: `raise AppError(...) from err`.
- Validate external input at the boundary (CLI args, request body, env, files).
- Use the `logging` module (or the repo's logger) with lazy formatting
  (`log.info("x=%s", x)`), not `print`. Never log secrets or tokens.

**Security**
- `subprocess.run([...])` with an argument list, never `shell=True` with
  interpolated input. Set `check=True` and a `timeout`.
- Parameterized SQL (see `sql.md` if it applies). `yaml.safe_load`, never
  `yaml.load` or `pickle` on untrusted data. Resolve and check user-supplied
  paths stay inside their base directory.

**Performance**
- `set`/`dict` for membership and lookups inside loops. Generators for large
  streams instead of building whole lists.
- In async code, never call blocking I/O (`requests`, `time.sleep`, sync DB
  drivers) on the event loop. Run independent awaits with `asyncio.gather` /
  `TaskGroup`, and set timeouts.

**Tests**
- Use the repo's test framework and fixtures (usually pytest). Test behavior
  through public functions, with one test per case; `parametrize` for tables
  of inputs. Cover the error path and an edge case for each new branch.
- No network or real clock in unit tests: use fixtures, `tmp_path`, fakes or
  the repo's mocking style.
