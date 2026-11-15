"""Build metadata shown on the /about page."""
import platform


def build_info() -> dict:
    return {"python": platform.python_version()}
