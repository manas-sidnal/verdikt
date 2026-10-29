import re


def slugify(text):
    """Turn a title into a URL slug."""
    text = re.sub(r"[^a-z0-9\s-]", "", text.lower())
    return re.sub(r"[\s-]+", "-", text).strip("-")
