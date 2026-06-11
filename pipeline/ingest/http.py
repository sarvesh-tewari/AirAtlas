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


def _throttle() -> None:
    global _last_request_at
    if _MIN_INTERVAL <= 0:
        return
    gap = time.time() - _last_request_at
    if gap < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - gap)
    _last_request_at = time.time()


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
    retries: int = 4,
    backoff: float = 2.0,
    use_cache: bool = True,
    cache_ttl: float | None = None,
) -> dict:
    """GET `url` and return parsed JSON, with disk cache + retry.

    cache_ttl: if set, a cached file older than this many seconds is ignored.
    """
    cache_file = CACHE_DIR / f"{_cache_key(url, params)}.json"
    if use_cache and cache_file.exists():
        if cache_ttl is None or (time.time() - cache_file.stat().st_mtime) < cache_ttl:
            return json.loads(cache_file.read_text())

    last_err: Exception | None = None
    for attempt in range(retries):
        wait = backoff * (2 ** attempt)
        try:
            _throttle()
            r = httpx.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code in (408, 429):
                # Timeout / rate-limit — retry, honoring Retry-After if present.
                ra = r.headers.get("Retry-After")
                wait = float(ra) if ra and ra.isdigit() else wait
                last_err = httpx.HTTPStatusError(
                    str(r.status_code), request=r.request, response=r)
            elif r.status_code >= 500:
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
                    and e.response.status_code not in (408, 429) \
                    and 400 <= e.response.status_code < 500:
                raise
            last_err = e
        if attempt < retries - 1:
            time.sleep(wait)

    raise RuntimeError(f"GET failed after {retries} attempts: {url}") from last_err
