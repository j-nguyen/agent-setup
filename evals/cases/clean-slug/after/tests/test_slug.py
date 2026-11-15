import pytest

from blog.slug import MAX_SLUG_LENGTH, slugify


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Hello, World!", "hello-world"),
        ("  Crème brûlée -- recipe  ", "creme-brulee-recipe"),
        ("C++ & Rust", "c-rust"),
        ("", "post"),
        ("!!!", "post"),
    ],
)
def test_slugify(title, expected):
    assert slugify(title) == expected


def test_slug_is_truncated_without_trailing_dash():
    slug = slugify("word " * 40)
    assert len(slug) <= MAX_SLUG_LENGTH
    assert not slug.endswith("-")
