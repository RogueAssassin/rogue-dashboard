"""Dependency-free, server-side collectors for service-card widgets.

Only compact display values and safe diagnostics leave this module. Secrets are
resolved from environment variable references at request time and are never
returned to the browser or written to the dashboard database.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar
import json
import os
import re
import socket
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


USER_AGENT = "Rogue-Dashboard/0.4.2"
MAX_RESPONSE = 2_000_000
LARGE_LIBRARY_RESPONSE = 24_000_000
TIMEOUT = 6
SUPPORTED_WIDGETS = {
    "bazarr",
    "pihole",
    "prowlarr",
    "qbittorrent",
    "radarr",
    "seerr",
    "sonarr",
    "tautulli",
}


def _base_url(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("A private service API URL is required.")
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("The service API URL must be a plain HTTP or HTTPS address.")
    return value


def _json_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    opener: Any = None,
    max_response: int = MAX_RESPONSE,
) -> Any:
    request = Request(
        url,
        method=method,
        data=data,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT, **(headers or {})},
    )
    open_request = opener.open if opener else urlopen
    with open_request(request, timeout=TIMEOUT) as response:
        payload = response.read(max_response + 1)
    if len(payload) > max_response:
        raise ValueError("The service returned an unexpectedly large response.")
    if not payload:
        return None
    return json.loads(payload)


def _text_request(url: str, *, opener: Any, data: bytes) -> str:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    request = Request(
        url,
        method="POST",
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
            "Origin": origin,
            "Referer": f"{origin}/",
        },
    )
    with opener.open(request, timeout=TIMEOUT) as response:
        payload = response.read(100_000)
    return payload.decode("utf-8", "replace").strip()


def _value(widget: dict[str, Any], *hints: str) -> str:
    refs = widget.get("secretRefs") if isinstance(widget.get("secretRefs"), list) else []
    bindings = widget.get("secretBindings") if isinstance(widget.get("secretBindings"), dict) else {}
    for hint in hints:
        ref = bindings.get(hint)
        if isinstance(ref, str) and _environment_value(ref):
            return _environment_value(ref)
    upper_hints = tuple(hint.upper() for hint in hints)
    for ref in refs:
        if isinstance(ref, str) and any(hint in ref.upper() for hint in upper_hints):
            value = _environment_value(ref)
            if value:
                return value
    if len(refs) == 1 and isinstance(refs[0], str):
        return _environment_value(refs[0])
    return ""


def _canonical_ref(ref: str) -> str:
    if ref.startswith("HOMEPAGE_VAR_"):
        return f"RGDASH_{ref.removeprefix('HOMEPAGE_VAR_')}"
    if ref.startswith("HOMEPAGE_"):
        return f"RGDASH_{ref.removeprefix('HOMEPAGE_')}"
    return ref


def _legacy_ref(ref: str) -> str:
    return f"HOMEPAGE_VAR_{ref.removeprefix('RGDASH_')}" if ref.startswith("RGDASH_") else ref


def _environment_value(ref: str) -> str:
    canonical = _canonical_ref(ref)
    canonical_value = os.environ.get(canonical, "")
    if canonical_value:
        return canonical_value
    if canonical == "RGDASH_QBITTORRENT_PASSWORD":
        legacy_qbit_value = os.environ.get("RGDASH_QBITTORRENT_API_KEY", "")
        if legacy_qbit_value:
            return legacy_qbit_value
    return os.environ.get(_legacy_ref(canonical), "")


def _metric(label: str, value: Any) -> dict[str, str]:
    return {"label": label, "value": str(value)}


def _number(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _format_bytes(value: Any, *, rate: bool = False) -> str:
    amount = max(0.0, float(value or 0))
    units = ("B", "KB", "MB", "GB", "TB")
    unit = 0
    while amount >= 1024 and unit < len(units) - 1:
        amount /= 1024
        unit += 1
    precision = 0 if unit < 2 else 1
    suffix = "/s" if rate else ""
    return f"{amount:.{precision}f} {units[unit]}{suffix}"


def _nested(value: Any, *path: str, default: Any = 0) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def _total(response: Any) -> int:
    if isinstance(response, dict):
        for key in ("total", "totalRecords", "recordsTotal"):
            if key in response:
                return _number(response[key])
        data = response.get("data")
        if isinstance(data, list):
            return len(data)
    return len(response) if isinstance(response, list) else 0


def _arr(widget: dict[str, Any], kind: str) -> list[dict[str, str]]:
    base = _base_url(widget.get("url"))
    api_key = _value(widget, "key", "apikey", "api_key")
    if not api_key:
        raise MissingSecrets
    if kind == "radarr" and not re.fullmatch(r"[0-9a-fA-F]{32}", api_key):
        raise ValueError("Radarr API key looks invalid. Copy the complete 32-character key from Settings > General > Security.")
    headers = {"X-Api-Key": api_key}
    unknown = "Movie" if kind == "radarr" else "Series"
    queue = _json_request(
        f"{base}/api/v3/queue?page=1&pageSize=1&includeUnknown{unknown}Items=false",
        headers=headers,
    )
    queued = _number(queue.get("totalRecords") if isinstance(queue, dict) else len(queue or []))
    if kind == "radarr":
        wanted = _json_request(f"{base}/api/v3/wanted/cutoff?page=1&pageSize=1", headers=headers)
        missing = _json_request(f"{base}/api/v3/wanted/missing?page=1&pageSize=1", headers=headers)
        movies = _json_request(
            f"{base}/api/v3/movie?includeAllMovieFiles=false",
            headers=headers,
            max_response=LARGE_LIBRARY_RESPONSE,
        )
        return [
            _metric("Wanted", _total(wanted)),
            _metric("Missing", _total(missing)),
            _metric("Queued", queued),
            _metric("Movies", len(movies) if isinstance(movies, list) else 0),
        ]
    wanted = _json_request(f"{base}/api/v3/wanted/missing?page=1&pageSize=1", headers=headers)
    series = _json_request(f"{base}/api/v3/series", headers=headers, max_response=LARGE_LIBRARY_RESPONSE)
    return [
        _metric("Wanted", _total(wanted)),
        _metric("Queued", queued),
        _metric("Series", len(series) if isinstance(series, list) else 0),
    ]


def _prowlarr(widget: dict[str, Any]) -> list[dict[str, str]]:
    base = _base_url(widget.get("url"))
    api_key = _value(widget, "key", "apikey", "api_key")
    if not api_key:
        raise MissingSecrets
    headers = {"X-Api-Key": api_key}
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    query = urlencode({"startDate": start.isoformat(), "endDate": end.isoformat()})
    stats = _json_request(f"{base}/api/v1/indexerstats?{query}", headers=headers)
    indexers = stats.get("indexers", []) if isinstance(stats, dict) else []
    return [
        _metric("Grabs", sum(_number(item.get("numberOfGrabs")) for item in indexers if isinstance(item, dict))),
        _metric("Queries", sum(_number(item.get("numberOfQueries")) for item in indexers if isinstance(item, dict))),
        _metric("Fail grabs", sum(_number(item.get("numberOfFailedGrabs")) for item in indexers if isinstance(item, dict))),
        _metric("Fail queries", sum(_number(item.get("numberOfFailedQueries")) for item in indexers if isinstance(item, dict))),
    ]


def _qbittorrent(widget: dict[str, Any]) -> list[dict[str, str]]:
    base = _base_url(widget.get("url"))
    username = _value(widget, "username", "user")
    password = _value(widget, "password", "pass")
    if not username and os.environ.get("RGDASH_QBITTORRENT_API_KEY", "") and password:
        username = "admin"
    if not username or not password:
        raise MissingSecrets
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    origin = f"{urlparse(base).scheme}://{urlparse(base).netloc}"
    common_headers = {"Origin": origin, "Referer": f"{origin}/"}
    try:
        login = _text_request(
            f"{base}/api/v2/auth/login",
            opener=opener,
            data=urlencode({"username": username, "password": password}).encode(),
        )
    except HTTPError as error:
        if error.code == 403:
            raise PermissionError(
                "qBittorrent rejected or temporarily banned the dashboard login. Verify the WebUI credentials and allowed subnet."
            ) from error
        raise
    if login.lower() != "ok.":
        raise PermissionError("qBittorrent rejected the WebUI username or password.")
    transfer = _json_request(f"{base}/api/v2/transfer/info", opener=opener, headers=common_headers)
    torrents = _json_request(f"{base}/api/v2/torrents/info", opener=opener, headers=common_headers)
    torrents = torrents if isinstance(torrents, list) else []
    leech_states = {"downloading", "forcedDL", "metaDL", "stalledDL", "checkingDL", "allocating"}
    seed_states = {"uploading", "forcedUP", "stalledUP", "checkingUP"}
    leeching = sum(item.get("state") in leech_states for item in torrents if isinstance(item, dict))
    seeding = sum(item.get("state") in seed_states for item in torrents if isinstance(item, dict))
    return [
        _metric("Download", _format_bytes(_nested(transfer, "dl_info_speed"), rate=True)),
        _metric("Upload", _format_bytes(_nested(transfer, "up_info_speed"), rate=True)),
        _metric("Leech", leeching),
        _metric("Seed", seeding),
    ]


def _tautulli(widget: dict[str, Any]) -> list[dict[str, str]]:
    base = _base_url(widget.get("url"))
    api_key = _value(widget, "key", "apikey", "api_key")
    if not api_key:
        raise MissingSecrets
    query = urlencode({"apikey": api_key, "cmd": "get_activity"})
    response = _json_request(f"{base}/api/v2?{query}")
    wrapper = response.get("response", {}) if isinstance(response, dict) else {}
    if wrapper.get("result") not in (None, "success"):
        raise PermissionError("The service rejected its credentials.")
    data = wrapper.get("data", {}) if isinstance(wrapper, dict) else {}
    return [
        _metric("Playing", _number(data.get("stream_count"))),
        _metric("Transcoding", _number(data.get("stream_count_transcode", data.get("transcode_streams")))),
        _metric("Bitrate", _format_bytes(_number(data.get("total_bandwidth")) * 1000, rate=True)),
    ]


def _bazarr(widget: dict[str, Any]) -> list[dict[str, str]]:
    base = _base_url(widget.get("url"))
    api_key = _value(widget, "key", "apikey", "api_key")
    if not api_key:
        raise MissingSecrets
    headers = {"X-API-KEY": api_key}
    episodes = _json_request(f"{base}/api/episodes/wanted?start=0&length=1", headers=headers)
    movies = _json_request(f"{base}/api/movies/wanted?start=0&length=1", headers=headers)

    return [_metric("Missing episodes", _total(episodes)), _metric("Missing movies", _total(movies))]


def _seerr(widget: dict[str, Any]) -> list[dict[str, str]]:
    base = _base_url(widget.get("url"))
    api_key = _value(widget, "key", "apikey", "api_key")
    if not api_key:
        raise MissingSecrets
    data = _json_request(f"{base}/api/v1/request/count", headers={"X-Api-Key": api_key})
    return [
        _metric("Pending", _number(_nested(data, "pending"))),
        _metric("Approved", _number(_nested(data, "approved"))),
        _metric("Processing", _number(_nested(data, "processing"))),
        _metric("Available", _number(_nested(data, "available"))),
    ]


def _pihole(widget: dict[str, Any]) -> list[dict[str, str]]:
    base = _base_url(widget.get("url"))
    password = _value(widget, "key", "password", "apikey", "api_key")
    headers: dict[str, str] = {}
    sid = ""
    if password:
        auth = _json_request(
            f"{base}/api/auth",
            method="POST",
            data=json.dumps({"password": password}).encode(),
            headers={"Content-Type": "application/json"},
        )
        session = auth.get("session", {}) if isinstance(auth, dict) else {}
        if session.get("valid") is not True or not session.get("sid"):
            raise PermissionError("The service rejected its credentials.")
        sid = str(session["sid"])
        headers["X-FTL-SID"] = sid
    try:
        summary = _json_request(f"{base}/api/stats/summary", headers=headers)
    finally:
        if sid:
            try:
                _json_request(f"{base}/api/auth", method="DELETE", headers={"X-FTL-SID": sid})
            except Exception:
                pass
    queries = _nested(summary, "queries", "total")
    blocked = _nested(summary, "queries", "blocked")
    percent = float(_nested(summary, "queries", "percent_blocked") or 0)
    clients = _nested(summary, "clients", "active")
    gravity = _nested(summary, "gravity", "domains_being_blocked")
    return [
        _metric("Queries", _number(queries)),
        _metric("Blocked", f"{_number(blocked)} ({percent:.0f}%)"),
        _metric("Gravity", _number(gravity)),
        _metric("Clients", _number(clients)),
    ]


class MissingSecrets(Exception):
    pass


COLLECTORS: dict[str, Callable[[dict[str, Any]], list[dict[str, str]]]] = {
    "bazarr": _bazarr,
    "pihole": _pihole,
    "prowlarr": _prowlarr,
    "qbittorrent": _qbittorrent,
    "radarr": lambda widget: _arr(widget, "radarr"),
    "seerr": _seerr,
    "sonarr": lambda widget: _arr(widget, "sonarr"),
    "tautulli": _tautulli,
}


def _safe_error(error: Exception) -> tuple[str, int | None]:
    if isinstance(error, HTTPError):
        if error.code in (401, 403):
            return "The service rejected its credentials.", error.code
        if error.code == 404:
            return "This service version does not expose the expected API endpoint.", error.code
        if error.code == 429:
            return "The service is rate-limiting dashboard requests.", error.code
        return f"The service API returned HTTP {error.code}.", error.code
    if isinstance(error, URLError):
        reason = error.reason
        if isinstance(reason, socket.gaierror):
            return "The container hostname could not be resolved. Ensure Rogue Dashboard is attached to media-net.", None
        if isinstance(reason, ConnectionRefusedError):
            return "The container resolved, but the configured private port refused the connection.", None
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return "The service API timed out from the dashboard container.", None
        return "The service API is unreachable from the dashboard container.", None
    if isinstance(error, (TimeoutError, socket.timeout, ConnectionError)):
        return "The service API is unreachable from the dashboard container.", None
    if isinstance(error, json.JSONDecodeError):
        return "The service returned an invalid API response.", None
    if isinstance(error, PermissionError):
        return str(error) or "The service rejected its credentials.", None
    if isinstance(error, ValueError):
        return str(error), None
    return "The service widget could not be refreshed.", None


def collect_widget(item: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    widget = item.get("widget") if isinstance(item.get("widget"), dict) else {}
    kind = str(widget.get("type", "")).strip().lower()
    result: dict[str, Any] = {
        "itemId": str(item.get("id", "")),
        "type": kind,
        "state": "error",
        "metrics": [],
    }
    if kind not in COLLECTORS:
        result.update(state="unsupported", message="This imported widget is not supported yet.")
        return result
    refs = list(dict.fromkeys(_canonical_ref(ref) for ref in widget.get("secretRefs", []) if isinstance(ref, str)))
    result["environment"] = [{"name": ref, "loaded": bool(_environment_value(ref))} for ref in refs]
    missing = [_canonical_ref(ref) for ref in refs if not _environment_value(ref)]
    if kind == "qbittorrent":
        legacy_password = bool(os.environ.get("RGDASH_QBITTORRENT_API_KEY", ""))
        has_username = bool(_value(widget, "username", "user") or legacy_password)
        has_password = bool(_value(widget, "password", "pass"))
        credentials_ready = has_username and has_password
    else:
        credentials_ready = not missing
    if not credentials_ready:
        result.update(
            state="configuration_required",
            message="Add the missing environment values to .env, then restart the dashboard.",
            missingRefs=missing or refs,
        )
        return result
    try:
        metrics = COLLECTORS[kind](widget)
        result.update(state="ok", metrics=metrics[:4], latencyMs=round((time.monotonic() - started) * 1000))
    except MissingSecrets:
        result.update(
            state="configuration_required",
            message="This widget needs environment-variable credentials.",
            missingRefs=[_canonical_ref(ref) for ref in refs],
        )
    except Exception as error:
        message, status = _safe_error(error)
        result.update(state="error", message=message)
        if status is not None:
            result["status"] = status
        result["latencyMs"] = round((time.monotonic() - started) * 1000)
    return result
