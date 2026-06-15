"""Shared HTTP helper: cached GET with retry/backoff.

- Responses are cached to `pipeline/.cache/` (gitignored), keyed by URL + params with
  any `api-key` stripped from the key (so cache files never embed secrets and stay stable
  across key rotation).
- Retries on transport errors and 5xx with exponential backoff. 4xx raises immediately
  (a 401/403 means a bad key — no point retrying).
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import time

import httpx

import os

CACHE_DIR = pathlib.Path(__file__).resolve().parents[1] / ".cache"

# Optional politeness throttle (seconds between requests). OpenAQ's free tier is ~60/min;
# set AIRATLAS_MIN_REQUEST_INTERVAL=1.1 to stay comfortably under it during big backfills.
_MIN_INTERVAL = float(os.environ.get("AIRATLAS_MIN_REQUEST_INTERVAL", "0") or "0")
_last_request_at = 0.0


def _throttle(interval: float | None = None) -> None:
    """Space requests at least `interval` seconds apart (defaults to the global throttle).

    A per-call override lets heavy endpoints (Open-Meteo's weighted archive API) pace much
    slower than OpenAQ without slowing the bulk AQ fetch.
    """
    global _last_request_at
    iv = _MIN_INTERVAL if interval is None else interval
    if iv <= 0:
        return
    gap = time.time() - _last_request_at
    if gap < iv:
        time.sleep(iv - gap)
    _last_request_at = time.time()


def _retry_wait(status_code: int | None, retry_after, attempt: int, backoff: float,
                rate_limit_floor: float = 60.0) -> float:
    """Seconds to wait before the next retry.

    A 429 honors a numeric Retry-After, else waits at least `rate_limit_floor`: Open-Meteo's
    weighted minutely limit needs ~a full minute to reset, and the short exponential backoff
    would otherwise exhaust retries inside the same minute. Other retryable errors (timeouts,
    5xx) use plain exponential backoff.
    """
    if retry_after is not None and str(retry_after).isdigit():
        return float(retry_after)
    exp = backoff * (2 ** attempt)
    return max(exp, rate_limit_floor) if status_code == 429 else exp


def _cache_key(url: str, params: dict | None) -> str:
    safe = {k: v for k, v in (params or {}).items() if k != "api-key"}
    blob = url + "?" + json.dumps(safe, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def get_json(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 30.0,
    retries: int = 5,
    backoff: float = 2.0,
    use_cache: bool = True,
    cache_ttl: float | None = None,
    min_interval: float | None = None,
) -> dict:
    """GET `url` and return parsed JSON, with disk cache + retry.

    cache_ttl: if set, a cached file older than this many seconds is ignored.
    min_interval: per-call request spacing override (e.g. for rate-strict endpoints).
    """
    cache_file = CACHE_DIR / f"{_cache_key(url, params)}.json"
    if use_cache and cache_file.exists():
        if cache_ttl is None or (time.time() - cache_file.stat().st_mtime) < cache_ttl:
            return json.loads(cache_file.read_text())

    last_err: Exception | None = None
    for attempt in range(retries):
        wait = _retry_wait(None, None, attempt, backoff)  # transient/timeout default
        try:
            _throttle(min_interval)
            r = httpx.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code in (403, 408, 429):
                # Timeout / rate-limit / transient 403 — retry. OpenAQ intermittently returns 403
                # on otherwise-valid requests (e.g. the /locations discovery call), so a single
                # blip must not fail a whole run; a genuinely bad key still fails after `retries`.
                wait = _retry_wait(r.status_code, r.headers.get("Retry-After"), attempt, backoff)
                last_err = httpx.HTTPStatusError(
                    str(r.status_code), request=r.request, response=r)
            elif r.status_code >= 500:
                wait = _retry_wait(r.status_code, None, attempt, backoff)
                last_err = httpx.HTTPStatusError(
                    f"server {r.status_code}", request=r.request, response=r)
            elif r.status_code >= 400:
                r.raise_for_status()  # other 4xx -> raise now, don't retry
            else:
                data = r.json()
                if use_cache:
                    CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    cache_file.write_text(json.dumps(data, ensure_ascii=False))
                return data
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as e:
            if isinstance(e, httpx.HTTPStatusError) and e.response is not None \
                    and e.response.status_code not in (403, 408, 429) \
                    and 400 <= e.response.status_code < 500:
                raise
            last_err = e
        if attempt < retries - 1:
            time.sleep(wait)

    raise RuntimeError(f"GET failed after {retries} attempts: {url}") from last_err
