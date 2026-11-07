"""Configurable per-user record quotas."""

import os


DEFAULT_MAX_OPPORTUNITIES_PER_USER = 5000


class OpportunityQuotaExceeded(Exception):
    """Raised when a user has reached the configured opportunity quota."""


def get_max_opportunities_per_user() -> int:
    raw_value = os.getenv("MAX_OPPORTUNITIES_PER_USER")
    if raw_value is None:
        return DEFAULT_MAX_OPPORTUNITIES_PER_USER

    try:
        value = int(raw_value.strip())
    except ValueError as error:
        raise RuntimeError("MAX_OPPORTUNITIES_PER_USER must be a positive integer") from error

    if value < 1:
        raise RuntimeError("MAX_OPPORTUNITIES_PER_USER must be a positive integer")
    return value


def validate_record_limit_configuration() -> None:
    """Fail startup when the opportunity quota setting is invalid."""
    get_max_opportunities_per_user()
