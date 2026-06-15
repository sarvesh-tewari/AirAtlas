"""Tests for the shared HTTP helper's retry-wait logic."""

import httpx
import pytest

from ingest import http


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}
        self.headers = {}
        self.request = httpx.Request("GET", "https://example.test")

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(str(self.status_code), request=self.request, response=self)


def _seq_get(monkeypatch, responses):
    calls = {"n": 0}

    def fake_get(*a, **k):
        r = responses[min(calls["n"], len(responses) - 1)]
        calls["n"] += 1
        return r

    monkeypatch.setattr(http.httpx, "get", fake_get)
    monkeypatch.setattr(http.time, "sleep", lambda *_: None)
    return calls


def test_get_json_retries_transient_403(monkeypatch):
    # OpenAQ intermittently 403s the /locations call; a single blip must not fail the run.
    calls = _seq_get(monkeypatch, [_Resp(403), _Resp(200, {"ok": True})])
    out = http.get_json("https://x", use_cache=False, backoff=0.0)
    assert out == {"ok": True}
    assert calls["n"] == 2          # retried after the 403


def test_get_json_gives_up_on_persistent_403(monkeypatch):
    # A genuinely forbidden key still fails (after retries) rather than looping forever.
    _seq_get(monkeypatch, [_Resp(403)])
    with pytest.raises((httpx.HTTPStatusError, RuntimeError)):
        http.get_json("https://x", use_cache=False, retries=3, backoff=0.0)


def test_get_json_does_not_retry_404(monkeypatch):
    # Other 4xx (e.g. 404) are real client errors -> raise immediately, no retry.
    calls = _seq_get(monkeypatch, [_Resp(404)])
    with pytest.raises(httpx.HTTPStatusError):
        http.get_json("https://x", use_cache=False, backoff=0.0)
    assert calls["n"] == 1


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
