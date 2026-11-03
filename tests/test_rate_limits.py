import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import job_analysis_routes, ocr_routes
from app.routes.ocr_routes import get_ocr_engine
from app.services.ocr_engine import OcrError


def register(client, email="user@example.com"):
    return client.post(
        "/auth/register",
        json={"email": email, "password": "StrongPass123"},
    )


def login(client, email="user@example.com", password="StrongPass123"):
    return client.post(
        "/auth/token",
        data={"username": email, "password": password},
    )


def client_at_ip(client, ip):
    return TestClient(client.app, client=(ip, 43210))


def assert_rate_limited(response):
    assert response.status_code == 429
    assert response.json().keys() == {"detail", "error_code"}
    assert response.json()["error_code"] == "rate_limited"
    assert int(response.headers["Retry-After"]) >= 1


@pytest.fixture(autouse=True)
def clean_rate_limit_state():
    try:
        from app.rate_limits import reset_rate_limit_state
    except ModuleNotFoundError:
        reset_rate_limit_state = None
    if reset_rate_limit_state:
        reset_rate_limit_state()
    yield
    if reset_rate_limit_state:
        reset_rate_limit_state()


class FakeEngine:
    def recognize(self, image):
        return "Python"


def png_bytes():
    from io import BytesIO
    from PIL import Image

    output = BytesIO()
    Image.new("RGB", (8, 8), "white").save(output, format="PNG")
    return output.getvalue()


def register_and_login(client, email="owner@example.com"):
    assert register(client, email).status_code == 201
    response = login(client, email)
    assert response.status_code == 200
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"


def test_login_rate_limit_runs_before_password_hash_and_returns_retry_after(
    client, monkeypatch
):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_PER_MINUTE", "30")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_EMAIL_PER_MINUTE", "2")
    assert register(client).status_code == 201

    from app.services import auth_service

    calls = []
    monkeypatch.setattr(
        auth_service,
        "verify_password",
        lambda password, hashed_password: calls.append((password, hashed_password)) or False,
    )

    first = login(client, password="wrong")
    second = login(client, password="wrong")
    third = login(client, password="wrong")

    assert first.status_code == 401
    assert second.status_code == 401
    assert_rate_limited(third)
    assert len(calls) == 2


def test_pair_limit_does_not_lock_email_from_another_ip(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_PER_MINUTE", "10")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_EMAIL_PER_MINUTE", "1")
    assert register(client).status_code == 201

    assert login(client, password="WrongPass123").status_code == 401
    assert_rate_limited(login(client, password="WrongPass123"))

    other_ip = client_at_ip(client, "198.51.100.27")
    assert login(other_ip).status_code == 200


def test_registration_has_a_separate_stricter_ip_limit(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_REGISTER_IP_PER_HOUR", "1")
    from app.services import auth_service

    hash_calls = []
    monkeypatch.setattr(
        auth_service,
        "hash_password",
        lambda password: hash_calls.append(password) or "test-hash",
    )

    assert register(client, "first@example.com").status_code == 201
    assert_rate_limited(register(client, "second@example.com"))
    assert hash_calls == ["StrongPass123"]

    other_ip = client_at_ip(client, "198.51.100.28")
    assert register(other_ip, "third@example.com").status_code == 201


def test_forwarded_for_is_ignored_without_explicit_trusted_proxy(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_PER_MINUTE", "1")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_EMAIL_PER_MINUTE", "10")
    monkeypatch.delenv("TRUSTED_PROXY_IPS", raising=False)

    first = client.post(
        "/auth/token",
        data={"username": "one@example.com", "password": "wrong"},
        headers={"X-Forwarded-For": "198.51.100.1"},
    )
    second = client.post(
        "/auth/token",
        data={"username": "two@example.com", "password": "wrong"},
        headers={"X-Forwarded-For": "198.51.100.2"},
    )

    assert first.status_code == 401
    assert_rate_limited(second)


def test_forwarded_for_uses_rightmost_untrusted_hop_only_when_proxy_is_trusted(
    client, monkeypatch
):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_PER_MINUTE", "1")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_EMAIL_PER_MINUTE", "10")
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "127.0.0.1")
    proxy_client = client_at_ip(client, "127.0.0.1")

    first = proxy_client.post(
        "/auth/token",
        data={"username": "one@example.com", "password": "wrong"},
        headers={"X-Forwarded-For": "203.0.113.99, 198.51.100.10"},
    )
    second = proxy_client.post(
        "/auth/token",
        data={"username": "two@example.com", "password": "wrong"},
        headers={"X-Forwarded-For": "198.51.100.10"},
    )

    assert first.status_code == 401
    assert_rate_limited(second)


def test_ocr_rate_limit_is_per_user_and_preserves_global_ocr_busy(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_OCR_PER_USER_PER_MINUTE", "1")
    register_and_login(client)
    second_user = client_at_ip(client, "198.51.100.44")
    register_and_login(second_user, "second@example.com")
    from app.rate_limits import reset_rate_limit_state

    reset_rate_limit_state()
    client.app.dependency_overrides[get_ocr_engine] = FakeEngine

    assert client.post("/ocr/extract", content=png_bytes()).status_code == 200
    assert_rate_limited(client.post("/ocr/extract", content=png_bytes()))
    assert second_user.post("/ocr/extract", content=png_bytes()).status_code == 200

    reset_rate_limit_state()
    assert ocr_routes._OCR_SLOT.acquire(blocking=False)
    try:
        busy = client.post("/ocr/extract", content=png_bytes())
    finally:
        ocr_routes._OCR_SLOT.release()
    assert busy.status_code == 503
    assert busy.json()["error_code"] == "ocr_busy"


def test_job_analysis_rate_limit_is_per_user(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_JOB_ANALYSIS_PER_USER_PER_MINUTE", "1")
    register_and_login(client)
    from app.rate_limits import reset_rate_limit_state

    reset_rate_limit_state()

    assert client.post("/job-analysis", json={"text": "Python"}).status_code == 200
    assert_rate_limited(client.post("/job-analysis", json={"text": "Python"}))



def test_rate_window_resets_with_a_fake_clock():
    from app.rate_limits import RateLimitManager

    now = [time.time()]
    manager = RateLimitManager(max_tracked_keys=5, clock=lambda: now[0])

    assert manager.check("login-ip", "192.0.2.1", 1, "minute").allowed
    blocked = manager.check("login-ip", "192.0.2.1", 1, "minute")
    assert not blocked.allowed
    assert blocked.retry_after >= 1

    now[0] += 61
    assert manager.check("login-ip", "192.0.2.1", 1, "minute").allowed
    assert manager.tracked_key_count == 1


def test_ocr_same_user_parallel_request_is_rate_limited(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_OCR_PER_USER_PER_MINUTE", "10")
    register_and_login(client)
    from app.rate_limits import reset_rate_limit_state

    reset_rate_limit_state()
    started = threading.Event()
    finish = threading.Event()

    class BlockingEngine:
        def recognize(self, image):
            started.set()
            assert finish.wait(timeout=5)
            return "Python"

    client.app.dependency_overrides[get_ocr_engine] = BlockingEngine
    second_client = client_at_ip(client, "198.51.100.46")
    second_client.headers["Authorization"] = client.headers["Authorization"]
    first_result = []
    first_request = threading.Thread(
        target=lambda: first_result.append(
            client.post("/ocr/extract", content=png_bytes())
        ),
        daemon=True,
    )
    first_request.start()
    assert started.wait(timeout=5)
    try:
        second = second_client.post("/ocr/extract", content=png_bytes())
        assert_rate_limited(second)
    finally:
        finish.set()
        first_request.join(timeout=5)

    assert not first_request.is_alive()
    assert first_result[0].status_code == 200


def test_job_analysis_same_user_parallel_request_is_rate_limited(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_JOB_ANALYSIS_PER_USER_PER_MINUTE", "10")
    register_and_login(client)
    from app.rate_limits import reset_rate_limit_state

    reset_rate_limit_state()
    started = threading.Event()
    finish = threading.Event()
    original = job_analysis_routes.analyze_job_text

    def blocking_analysis(*args, **kwargs):
        started.set()
        assert finish.wait(timeout=5)
        return original(*args, **kwargs)

    monkeypatch.setattr(job_analysis_routes, "analyze_job_text", blocking_analysis)
    second_client = client_at_ip(client, "198.51.100.47")
    second_client.headers["Authorization"] = client.headers["Authorization"]
    first_result = []
    first_request = threading.Thread(
        target=lambda: first_result.append(
            client.post("/job-analysis", json={"text": "Python"})
        ),
        daemon=True,
    )
    first_request.start()
    assert started.wait(timeout=5)
    try:
        second = second_client.post("/job-analysis", json={"text": "Python"})
        assert_rate_limited(second)
    finally:
        finish.set()
        first_request.join(timeout=5)

    assert not first_request.is_alive()
    assert first_result[0].status_code == 200


def test_limiter_bounds_and_expires_unique_identifier_state():
    from app.rate_limits import RateLimitManager

    now = [time.time()]
    manager = RateLimitManager(max_tracked_keys=3, clock=lambda: now[0])

    assert manager.check("login-pair", "one", 1, "minute").allowed
    assert manager.check("login-pair", "two", 1, "minute").allowed
    assert manager.check("login-pair", "three", 1, "minute").allowed
    full = manager.check("login-pair", "four", 1, "minute")
    assert not full.allowed
    assert full.retry_after >= 1
    assert manager.tracked_key_count == 3

    now[0] += 61
    assert manager.check("login-pair", "four", 1, "minute").allowed
    assert manager.tracked_key_count <= 3


def test_user_concurrency_slots_are_isolated_and_idempotently_released():
    from app.rate_limits import UserSlotLimiter

    slots = UserSlotLimiter()
    first = slots.acquire(100, scope="ocr")
    other_user = slots.acquire(200, scope="ocr")
    other_operation = slots.acquire(100, scope="job-analysis")
    assert first is not None and other_user is not None and other_operation is not None
    assert slots.acquire(100, scope="ocr") is None

    first.release()
    first.release()
    replacement = slots.acquire(100, scope="ocr")
    assert replacement is not None
    assert slots.active_count == 3
    replacement.release()
    other_user.release()
    other_operation.release()
    assert slots.active_count == 0


def test_ocr_worker_releases_user_slot_after_engine_error(monkeypatch):
    from app.rate_limits import user_slot_limiter

    lease = user_slot_limiter.acquire(9001)
    assert lease is not None
    assert ocr_routes._OCR_SLOT.acquire(blocking=False)

    def fail(*args, **kwargs):
        raise OcrError("ocr_engine_failed", "synthetic failure")

    monkeypatch.setattr(ocr_routes, "extract_text", fail)
    try:
        with pytest.raises(OcrError):
            ocr_routes._run_reserved_ocr(png_bytes(), FakeEngine(), lease)
    finally:
        # Return exactly the reservation this test acquired, whether or not the
        # worker released it; the assertion below records the expected release.
        available = ocr_routes._OCR_SLOT.acquire(blocking=False)
        ocr_routes._OCR_SLOT.release()
    assert available

    replacement = user_slot_limiter.acquire(9001)
    assert replacement is not None
    replacement.release()


def test_ocr_user_slot_stays_held_until_worker_finishes_after_waiter_cancel():
    from app.rate_limits import user_slot_limiter

    started = threading.Event()
    finish = threading.Event()
    lease = user_slot_limiter.acquire(9002)
    assert lease is not None
    assert ocr_routes._OCR_SLOT.acquire(blocking=False)

    class BlockingEngine:
        def recognize(self, image):
            started.set()
            assert finish.wait(timeout=5)
            return "Python"

    future = ocr_routes._submit_reserved_ocr(png_bytes(), BlockingEngine(), lease)
    assert started.wait(timeout=5)

    async def cancel_waiter():
        waiter = asyncio.create_task(ocr_routes._await_ocr_worker(future))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter

    try:
        asyncio.run(cancel_waiter())
        assert user_slot_limiter.acquire(9002) is None
    finally:
        finish.set()

    assert future.result(timeout=5).text == "Python"
    replacement = user_slot_limiter.acquire(9002)
    assert replacement is not None
    replacement.release()


def test_job_analysis_worker_releases_user_slot_after_failure(monkeypatch):
    from app.rate_limits import user_slot_limiter

    lease = user_slot_limiter.acquire(9003)
    assert lease is not None

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic analysis failure")

    monkeypatch.setattr(job_analysis_routes, "analyze_job_text", fail)
    with pytest.raises(RuntimeError, match="synthetic analysis failure"):
        job_analysis_routes._run_analysis_and_release(None, 9003, "Python", lease)

    replacement = user_slot_limiter.acquire(9003)
    assert replacement is not None
    replacement.release()


def test_job_analysis_worker_holds_user_slot_until_thread_finishes():
    from app.rate_limits import user_slot_limiter

    started = threading.Event()
    finish = threading.Event()
    lease = user_slot_limiter.acquire(9004)
    assert lease is not None

    def blocking_analysis(*args, **kwargs):
        started.set()
        assert finish.wait(timeout=5)
        return "done"

    original = job_analysis_routes.analyze_job_text
    job_analysis_routes.analyze_job_text = blocking_analysis
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                job_analysis_routes._run_analysis_and_release,
                None,
                9004,
                "Python",
                lease,
            )
            assert started.wait(timeout=5)
            assert user_slot_limiter.acquire(9004) is None
            # Cancelling the waiter cannot stop an already-running worker.
            assert future.cancel() is False
            finish.set()
            assert future.result(timeout=5) == "done"
    finally:
        job_analysis_routes.analyze_job_text = original

    replacement = user_slot_limiter.acquire(9004)
    assert replacement is not None
    replacement.release()
