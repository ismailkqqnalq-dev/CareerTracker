"""Argon2 her hash için ~64 MB bellek kullanır; aynı anda çalışan hash sayısı sınırlı olmalı."""
import threading
from concurrent.futures import ThreadPoolExecutor

import app.security as security


class BlockingHasher:
    """Testin izni gelene kadar her hash'i açık tutar ve kaçının aynı anda çalıştığını sayar."""

    def __init__(self):
        self.running = threading.Condition()
        self.active = 0
        self.max_active = 0
        self.release = threading.Event()

    def _run(self):
        with self.running:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.running.notify_all()
        self.release.wait(timeout=10)
        with self.running:
            self.active -= 1
        return "hash"

    def hash(self, _password):
        return self._run()

    def verify(self, _password, _hashed):
        self._run()
        return True


def test_concurrent_hashing_never_exceeds_the_limit(monkeypatch):
    limit = security.MAX_CONCURRENT_PASSWORD_HASHES
    fake = BlockingHasher()
    monkeypatch.setattr(security, "password_hash", fake)

    with ThreadPoolExecutor(max_workers=limit * 3) as pool:
        jobs = [pool.submit(security.hash_password, "x") for _ in range(limit * 2)]
        jobs += [pool.submit(security.verify_password, "x", "h") for _ in range(limit)]
        with fake.running:
            assert fake.running.wait_for(lambda: fake.active == limit, timeout=10)
        # Sınır kadar hash çalışırken boşta yer kalmamalı; geri kalanlar sırada bekler.
        assert not security._password_hash_slots.acquire(blocking=False)
        fake.release.set()
        results = [job.result() for job in jobs]

    assert fake.max_active == limit
    assert results.count("hash") == limit * 2 and results.count(True) == limit


def test_real_hash_still_verifies():
    hashed = security.hash_password("GucluSifre123")

    assert security.verify_password("GucluSifre123", hashed)
    assert not security.verify_password("YanlisSifre1", hashed)
