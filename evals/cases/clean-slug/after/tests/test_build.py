import subprocess

from blog import build
from blog.build import build_info


def test_build_info_has_python_version():
    assert "python" in build_info()


def test_build_info_commit_unknown_without_git(monkeypatch):
    def boom(*args, **kwargs):
        raise FileNotFoundError("git")

    build._git_commit.cache_clear()
    monkeypatch.setattr(subprocess, "run", boom)
    assert build_info()["commit"] == "unknown"
    build._git_commit.cache_clear()
