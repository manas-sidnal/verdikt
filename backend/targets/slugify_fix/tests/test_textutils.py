from textutils import slugify


def test_lowercases():
    assert slugify("Hello") == "hello"


def test_spaces_become_hyphens():
    assert slugify("hello world") == "hello-world"


def test_punctuation_removed():
    assert slugify("Hello, World!") == "hello-world"


def test_collapses_repeated_whitespace():
    assert slugify("a   b") == "a-b"


def test_strips_leading_and_trailing_separators():
    assert slugify("  hi  ") == "hi"


def test_empty_string():
    assert slugify("") == ""
