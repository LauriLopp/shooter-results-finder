"""HTTP access with an on-disk cache and a CA bundle that fixes protokollitaja.eu.

protokollitaja.eu serves its certificate without the Let's Encrypt "YE1"
intermediate. Browsers fetch it automatically; Python does not. We ship that
intermediate (certs/letsencrypt-ye1.pem) and append it to certifi's bundle, so
certificate verification stays fully enabled.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from importlib import resources
from pathlib import Path

import certifi
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "shooter-results-finder/1.0 (+https://github.com/LauriLopp/shooter-results-finder)"
TIMEOUT = 60

# Minimum seconds between requests per host (SIUS answers bursts with HTTP 429).
HOST_INTERVAL = {"results.sius.com": 0.6}

# Listing pages change as new results are published; documents rarely do.
LISTING_TTL = 6 * 3600
DOCUMENT_TTL = None  # forever


def cache_dir() -> Path:
    d = Path(os.environ.get("RESULTS_SCRAPER_CACHE", Path.home() / ".cache" / "results_scraper"))
    d.mkdir(parents=True, exist_ok=True)
    return d


_bundle_lock = threading.Lock()


def ca_bundle() -> str:
    """certifi's CA list plus the Let's Encrypt YE1 intermediate."""
    path = cache_dir() / "ca-bundle.pem"
    with _bundle_lock:
        extra = resources.files("results_scraper").joinpath("certs/letsencrypt-ye1.pem").read_text()
        content = Path(certifi.where()).read_text() + "\n" + extra
        if not path.exists() or path.read_text() != content:
            path.write_text(content)
    return str(path)


_local = threading.local()


def session() -> requests.Session:
    s = getattr(_local, "session", None)
    if s is None:
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        retry = Retry(
            total=6,
            backoff_factor=2.0,
            status_forcelist=(429, 500, 502, 503, 504),
            respect_retry_after_header=True,
        )
        s.mount("https://", HTTPAdapter(max_retries=retry))
        s.mount("http://", HTTPAdapter(max_retries=retry))
        s.verify = ca_bundle()
        _local.session = s
    return s


def _cache_path(key: str) -> Path:
    h = hashlib.sha256(key.encode()).hexdigest()
    d = cache_dir() / "http" / h[:2]
    d.mkdir(parents=True, exist_ok=True)
    return d / h


_host_locks: dict[str, threading.Lock] = {}
_host_last: dict[str, float] = {}
_host_guard = threading.Lock()


def _throttle(url: str) -> None:
    from urllib.parse import urlsplit

    host = urlsplit(url).hostname or ""
    interval = HOST_INTERVAL.get(host)
    if not interval:
        return
    with _host_guard:
        lock = _host_locks.setdefault(host, threading.Lock())
    with lock:
        wait = _host_last.get(host, 0.0) + interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _host_last[host] = time.monotonic()


def fetch(url: str, ttl: float | None = DOCUMENT_TTL, *, refresh: bool = False) -> bytes:
    """GET a URL, using the on-disk cache when it is fresh enough."""
    path = _cache_path(url)
    if not refresh and path.exists():
        age = time.time() - path.stat().st_mtime
        if ttl is None or age < ttl:
            return path.read_bytes()
    _throttle(url)
    resp = session().get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(resp.content)
    tmp.replace(path)
    return resp.content


def fetch_text(url: str, ttl: float | None = LISTING_TTL, *, refresh: bool = False) -> str:
    data = fetch(url, ttl, refresh=refresh)
    return data.decode("utf-8", errors="replace")


def fetch_json(url: str, ttl: float | None = LISTING_TTL, *, refresh: bool = False):
    import json

    return json.loads(fetch(url, ttl, refresh=refresh))
