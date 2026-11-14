"""The one polite Wikimedia client every Track A fetch goes through (PLAN section 0, A1).

Read only: Action API calls must use a read action. Every response is cached under data/raw/ and never
fetched twice. One request at a time by default (WIKI_PARALLEL, capped at 3), maxlag=5 on Action API calls,
Retry-After honoured on 429 and on maxlag errors.
"""

import gzip
import hashlib
import json
import os
import threading
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "raw"
USER_AGENT = (
    f"Parallax/0.1 (https://github.com/timkicker/attention-is-all-we-have) python-requests/{requests.__version__}"
)
READ_ACTIONS = {"query", "parse", "compare", "sitematrix", "wbgetentities"}
MAX_429_TRIES = 6
MAX_5XX_RETRIES = 3

SESSION = requests.Session()
SESSION.headers["User-Agent"] = USER_AGENT
STATS: dict[str, float] = {}
_STATS_LOCK = threading.Lock()


class WikiError(RuntimeError):
    pass


class RateLimited(WikiError):
    """Wikimedia kept answering 429 (or maxlag) after every retry; wait retry_after_s before asking again."""

    def __init__(self, msg: str, retry_after_s: float) -> None:
        super().__init__(msg)
        self.retry_after_s = retry_after_s


GIVE_UP_COOLDOWN_S = 120.0  # after a give-up, callers wait this long before the next try
_cooldown_until = 0.0
_local = threading.local()


def on_wait(callback) -> None:
    """Set (or clear with None) a callback(seconds) for this thread, called before each 429/maxlag sleep."""
    _local.on_wait = callback


def cooldown_left() -> float:
    """Seconds until the client wants to be asked again after it gave up on a 429, 0 when free."""
    return max(0.0, _cooldown_until - time.monotonic())


def reset_stats() -> None:
    with _STATS_LOCK:
        STATS.clear()
        STATS.update(calls=0, hits=0, r429=0, r5xx=0, wait_s=0.0)


reset_stats()


def parallel_limit() -> int:
    return max(1, min(3, int(os.environ.get("WIKI_PARALLEL") or 1)))


_SEM = threading.BoundedSemaphore(parallel_limit())


def _bump(key: str, by: float = 1) -> None:
    with _STATS_LOCK:
        STATS[key] += by


def cache_key(url: str, params: dict) -> str:
    canon = url + json.dumps(sorted((str(k), str(v)) for k, v in params.items()), ensure_ascii=False)
    return hashlib.sha1(canon.encode("utf-8")).hexdigest()


def _cache_path(key: str) -> Path:
    return CACHE_DIR / key[:2] / f"{key}.json.gz"


def stats_line() -> str:
    return " ".join(f"{k}={round(v, 1) if isinstance(v, float) else v}" for k, v in STATS.items())


def get(url: str, params: dict | None = None, *, backoff: float = 5.0, timeout: float = 60.0) -> dict:
    """GET a Wikimedia URL and return its JSON, from the disk cache when present."""
    params = dict(params or {})
    is_action = url.endswith("/api.php")
    if is_action:
        action = params.get("action", "query")
        if action not in READ_ACTIONS:
            raise ValueError(f"read-only client: action {action!r} is not allowed")
        params.setdefault("format", "json")
        params.setdefault("maxlag", 5)
    key = cache_key(url, params)
    path = _cache_path(key)
    if path.exists():
        _bump("hits")
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)

    wait = backoff
    tries_429 = 0
    retries_5xx = 0
    while True:
        with _SEM:
            _bump("calls")
            resp = SESSION.get(url, params=params, timeout=timeout)
        lagged = False
        if resp.status_code == 200 and is_action:
            try:
                body = resp.json()
            except ValueError as e:
                raise WikiError(f"not JSON from {url}") from e
            lagged = isinstance(body.get("error"), dict) and body["error"].get("code") == "maxlag"
        if resp.status_code == 429 or lagged:
            tries_429 += 1
            _bump("r429")
            ra = resp.headers.get("Retry-After")
            sleep_s = float(ra) if ra and ra.replace(".", "", 1).isdigit() else wait
            if tries_429 >= MAX_429_TRIES:
                global _cooldown_until
                retry_after = max(sleep_s, GIVE_UP_COOLDOWN_S)
                _cooldown_until = max(_cooldown_until, time.monotonic() + retry_after)
                raise RateLimited(f"429/maxlag {tries_429} times for {url}", retry_after)
            wait *= 2
            _bump("wait_s", sleep_s)
            hook = getattr(_local, "on_wait", None)
            if hook:
                hook(sleep_s)
            time.sleep(sleep_s)
            continue
        if resp.status_code >= 500:
            retries_5xx += 1
            _bump("r5xx")
            if retries_5xx > MAX_5XX_RETRIES:
                raise WikiError(f"HTTP {resp.status_code} after {MAX_5XX_RETRIES} retries for {url}")
            time.sleep(backoff * retries_5xx)
            _bump("wait_s", backoff * retries_5xx)
            continue
        if resp.status_code != 200:
            raise WikiError(f"HTTP {resp.status_code} for {url}")
        body = resp.json()
        if is_action and "error" in body:
            raise WikiError(f"API error {body['error'].get('code')}: {body['error'].get('info')}")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False)
        tmp.replace(path)
        return body


def api_url(lang: str) -> str:
    return f"https://{lang}.wikipedia.org/w/api.php"


def query_all(lang: str, params: dict, cont_key: str = "continue"):
    """Yield every page of an Action API query, following `continue`."""
    params = {"action": "query", "formatversion": 2, **params}
    cont: dict = {}
    while True:
        body = get(api_url(lang), {**params, **cont})
        yield body
        if cont_key not in body:
            return
        cont = body[cont_key]


TARGET_LANGS = ("sv", "de", "en", "ru", "et", "uk")


def smoke() -> None:
    """fetch-smoke: langlinks of fi Talvisota, the six target titles and STATS."""
    body = get(
        api_url("fi"),
        {
            "action": "query",
            "prop": "langlinks|pageprops",
            "lllimit": "max",
            "titles": "Talvisota",
            "formatversion": 2,
        },
    )
    page = body["query"]["pages"][0]
    links = {ll["lang"]: ll["title"] for ll in page.get("langlinks", [])}
    print(f"fi {page['title']} page_id={page['pageid']} wikidata={page.get('pageprops', {}).get('wikibase_item')}")
    for lang in TARGET_LANGS:
        print(f"{lang} {links.get(lang, '-')}")
    print(stats_line())


if __name__ == "__main__":
    smoke()
