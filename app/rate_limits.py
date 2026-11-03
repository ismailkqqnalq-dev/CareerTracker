"""Process-local API rate limits and per-user work slots."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import ipaddress
import math
import os
import threading
import time
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from limits import RateLimitItemPerHour, RateLimitItemPerMinute
from limits.strategies import FixedWindowRateLimiter
from limits.storage import MemoryStorage


def positive_int_env(name: str, default: int) -> int:
    """Read a positive integer setting; reject unsafe or ambiguous values."""
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be a positive integer") from error
    if value < 1:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after: int = 0


class RateLimitManager:
    """Fixed-window limiter with an explicit cap and lazy expired-key cleanup."""

    def __init__(
        self,
        max_tracked_keys: int | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.storage = MemoryStorage()
        self.limiter = FixedWindowRateLimiter(self.storage)
        self.max_tracked_keys = (
            max_tracked_keys
            if max_tracked_keys is not None
            else positive_int_env("RATE_LIMIT_MAX_TRACKED_KEYS", 10_000)
        )
        if self.max_tracked_keys < 1:
            raise ValueError("max_tracked_keys must be positive")
        self.clock = clock
        # Values contain only a hashed identifier, never an email address.
        self._tracked: dict[str, tuple[float, Any, str]] = {}
        self._lock = threading.RLock()

    @property
    def tracked_key_count(self) -> int:
        with self._lock:
            return len(self._tracked)

    def _prune_expired(self, now: float) -> None:
        expired = [
            key
            for key, (expires_at, _item, _identifier) in self._tracked.items()
            if expires_at <= now
        ]
        for key in expired:
            _expires_at, item, identifier = self._tracked.pop(key)
            self.limiter.clear(item, identifier)

    def check(
        self,
        scope: str,
        identifier: str | int,
        limit: int,
        period: str = "minute",
    ) -> RateLimitDecision:
        if limit < 1:
            raise ValueError("limit must be positive")
        if period == "minute":
            item = RateLimitItemPerMinute(limit, namespace=f"CareerTracker/{scope}")
        elif period == "hour":
            item = RateLimitItemPerHour(limit, namespace=f"CareerTracker/{scope}")
        else:
            raise ValueError("period must be minute or hour")

        safe_identifier = hashlib.sha256(
            f"{scope}:{identifier}".encode("utf-8")
        ).hexdigest()
        storage_key = item.key_for(safe_identifier)
        now = self.clock()

        with self._lock:
            self._prune_expired(now)
            if (
                storage_key not in self._tracked
                and len(self._tracked) >= self.max_tracked_keys
            ):
                earliest_expiry = min(
                    (entry[0] for entry in self._tracked.values()),
                    default=now + 1,
                )
                return RateLimitDecision(
                    allowed=False,
                    retry_after=max(1, math.ceil(earliest_expiry - now)),
                )

            allowed = self.limiter.hit(item, safe_identifier)
            stats = self.limiter.get_window_stats(item, safe_identifier)
            expires_at = max(now + 1, float(stats.reset_time))
            self._tracked[storage_key] = (expires_at, item, safe_identifier)
            retry_after = 0 if allowed else max(
                1, math.ceil(expires_at - now)
            )
            return RateLimitDecision(allowed=allowed, retry_after=retry_after)

    def reset(self) -> None:
        """Clear counters for isolated tests; never called by request handlers."""
        with self._lock:
            self.storage.reset()
            self._tracked.clear()


class UserSlotLease:
    def __init__(self, limiter: UserSlotLimiter, key: tuple[str, str]) -> None:
        self._limiter = limiter
        self._key = key
        self._released = False
        self._lock = threading.Lock()

    def release(self) -> None:
        with self._lock:
            if self._released:
                return
            self._released = True
        self._limiter._release(self._key)


class UserSlotLimiter:
    """One in-flight expensive operation per user and operation type."""

    def __init__(self) -> None:
        self._active: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._active)

    def acquire(self, user_id: str | int, scope: str = "default") -> UserSlotLease | None:
        key = (scope, str(user_id))
        with self._lock:
            if key in self._active:
                return None
            self._active.add(key)
        return UserSlotLease(self, key)

    def _release(self, key: tuple[str, str]) -> None:
        with self._lock:
            self._active.discard(key)

    def reset(self) -> None:
        """Clear slots for isolated tests only."""
        with self._lock:
            self._active.clear()


rate_limit_manager = RateLimitManager()
user_slot_limiter = UserSlotLimiter()


def reset_rate_limit_state() -> None:
    rate_limit_manager.reset()
    user_slot_limiter.reset()


def _trusted_proxy_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    raw_value = os.getenv("TRUSTED_PROXY_IPS", "")
    networks = []
    try:
        for item in raw_value.split(","):
            if item.strip():
                networks.append(ipaddress.ip_network(item.strip(), strict=False))
    except ValueError:
        # Invalid proxy configuration fails closed: ignore forwarded headers.
        return []
    return networks


def get_client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    try:
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return peer

    trusted_networks = _trusted_proxy_networks()
    if not any(peer_ip in network for network in trusted_networks):
        return peer

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return peer

    try:
        chain = [ipaddress.ip_address(value.strip()) for value in forwarded.split(",")]
    except ValueError:
        return peer

    # Walk from the trusted peer toward the client. Ignore spoofable entries
    # farther left once the first untrusted hop is reached.
    for address in reversed([*chain, peer_ip]):
        if any(address in network for network in trusted_networks):
            continue
        return address.compressed
    return peer


def rate_limited_response(retry_after: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "İstek sınırına ulaşıldı; lütfen biraz bekleyip tekrar deneyin.",
            "error_code": "rate_limited",
        },
        headers={
            "Cache-Control": "no-store",
            "Retry-After": str(max(1, retry_after)),
        },
    )
