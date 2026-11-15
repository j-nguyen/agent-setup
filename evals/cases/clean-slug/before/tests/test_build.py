from blog.build import build_info


def test_build_info_has_python_version():
    assert "python" in build_info()
