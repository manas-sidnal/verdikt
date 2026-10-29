def slugify(text):
    """Turn a title into a URL slug."""
    cleaned = "".join(c for c in text.lower() if c.isalnum() or c == " ")
    return cleaned.replace(" ", "-")
