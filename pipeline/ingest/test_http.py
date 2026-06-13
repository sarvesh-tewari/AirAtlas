"""Tests for the shared HTTP helper's retry-wait logic."""

from ingest import http


def test_retry_wait_honors_numeric_retry_after():
    assert http._retry_wait(429, "30", attempt=0, backoff=2.0) == 30.0


def test_retry_wait_429_floors_at_a_minute_without_retry_after():
    # Open-Meteo's weighted minutely limit needs ~a full minute to reset; the short exponential
    # backoff (<=16s) would exhaust retries inside the same minute and fail. Floor 429 waits at 60s.
    assert http._retry_wait(429, None, attempt=0, backoff=2.0) >= 60.0
    assert http._retry_wait(429, None, attempt=1, backoff=2.0) >= 60.0


def test_retry_wait_5xx_uses_exponential_backoff():
    # Transient server errors recover fast, so keep the short exponential backoff (no minute floor).
    assert http._retry_wait(500, None, attempt=0, backoff=2.0) == 2.0
    assert http._retry_wait(500, None, attempt=2, backoff=2.0) == 8.0
