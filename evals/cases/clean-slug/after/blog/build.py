"""Build metadata shown on the /about page."""
import hashlib
import platform
import subprocess
from functools import cache


@cache
def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip() or "unknown"


def build_info() -> dict:
    commit = _git_commit()
    return {
        "python": platform.python_version(),
        "commit": commit,
        # Short, stable identifier for cache-busting static assets; not used for security.
        "asset_version": hashlib.md5(commit.encode()).hexdigest()[:8],
    }
