import unicodedata
from urllib.parse import urlsplit


def validate_http_url(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    if any(
        char.isspace() or unicodedata.category(char) == "Cc"
        for char in value
    ):
        raise ValueError("URL cannot contain whitespace or control characters")
    try:
        parsed = urlsplit(value)
    except ValueError as error:
        raise ValueError("URL must be a valid HTTP or HTTPS URL") from error
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must use HTTP or HTTPS and include a host")
    return value
