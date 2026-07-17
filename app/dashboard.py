#!/usr/bin/env python3
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import hmac
from http import HTTPStatus
from http.client import HTTPConnection
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import sys
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
import zipfile

from importer import DEFAULT_DASHBOARD, import_homepage, suggested_widget
from integrations import SUPPORTED_WIDGETS, collect_widget


VERSION = "1.0.1"
PORT = int(os.environ.get("PORT", "8080"))
AGENT_PORT = int(os.environ.get("AGENT_PORT", "8081"))
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
STATIC_DIR = Path(os.environ.get("STATIC_DIR", Path(__file__).with_name("static")))
CUSTOM_DIR = Path(os.environ.get("CUSTOM_DIR", "/custom"))
DOCKER_SOCKET = os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock")
DOCKER_AGENT_URL = os.environ.get("DOCKER_AGENT_URL", "")
DOCKER_AGENT_TOKEN = os.environ.get("DOCKER_AGENT_TOKEN", "")
SECURE_COOKIES = os.environ.get("SECURE_COOKIES", "false").lower() == "true"
TRUST_PROXY_HEADERS = os.environ.get("RGDASH_TRUST_PROXY_HEADERS", "true").lower() == "true"
CONFIGURED_ALLOWED_HOSTS = {
    host.strip().lower().rstrip(".")
    for host in os.environ.get("RGDASH_ALLOWED_HOSTS", "").split(",")
    if host.strip()
}
ALLOWED_HOSTS = set(CONFIGURED_ALLOWED_HOSTS)
ALLOWED_HOSTS.update({"localhost", "127.0.0.1", "::1", "dashboard", "rogue-dashboard"})
ROGUEROUTE_PUBLIC_URL = os.environ.get("RGDASH_ROGUEROUTE_URL", "").strip()
if urlparse(ROGUEROUTE_PUBLIC_URL).scheme not in ("http", "https"):
    ROGUEROUTE_PUBLIC_URL = ""
SESSION_COOKIE = "rogue_session"
MAX_BODY = 2_000_000
MAX_ARCHIVE_ENTRIES = 100
MAX_ARCHIVE_UNCOMPRESSED = 5_000_000
MAX_CUSTOM_ASSET = 10_000_000
CUSTOM_ASSET_SUFFIXES = {".avif", ".gif", ".ico", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
ROGUEROUTE_WEB_HEALTH_URL = "http://rogueroute-gpx-web:9080/api/health"
ROGUEROUTE_OSRM_HEALTH_URL = "http://rogueroute-gpx-web:9080/api/health/osrm"
ROGUEROUTE_MANAGER_HEALTH_URL = "http://rogueroute-gpx-manager:9090/health"


class SetupCompleted(Exception):
    """Raised when another setup request has already created the administrator."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp(value: Any, minimum: int, maximum: int, fallback: int) -> int:
    return max(minimum, min(maximum, value)) if isinstance(value, int) and not isinstance(value, bool) else fallback


def text(value: Any, maximum: int, fallback: str = "") -> str:
    return value[:maximum] if isinstance(value, str) else fallback


def canonical_env_ref(value: str) -> str:
    if value.startswith("HOMEPAGE_VAR_"):
        return f"RGDASH_{value.removeprefix('HOMEPAGE_VAR_')}"
    if value.startswith("HOMEPAGE_"):
        return f"RGDASH_{value.removeprefix('HOMEPAGE_')}"
    return value


def validate_dashboard(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Dashboard must be an object")
    raw_meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    stored_version = raw.get("version") if isinstance(raw.get("version"), int) else 1
    allowed_themes = ("neon", "midnight", "graphite", "ocean", "ember", "light")
    stored_theme = raw_meta.get("theme") if raw_meta.get("theme") in allowed_themes else "midnight"
    theme = "neon" if stored_version < 2 and stored_theme == "midnight" else stored_theme
    accent = text(raw_meta.get("accent"), 7, "#ff2bd6" if theme == "neon" else "#7c5cff")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        accent = "#ff2bd6" if theme == "neon" else "#7c5cff"
    accent_secondary = text(raw_meta.get("accentSecondary"), 7, "#00e5ff")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent_secondary):
        accent_secondary = "#00e5ff"
    result: dict[str, Any] = {
        "version": 7,
        "meta": {
            "title": text(raw_meta.get("title"), 100, "My Docker Dashboard").strip() or "My Docker Dashboard",
            "subtitle": text(raw_meta.get("subtitle"), 180, "Your self-hosted command centre"),
            "theme": theme,
            "accent": accent,
            "accentSecondary": accent_secondary,
            "background": text(raw_meta.get("background"), 1000),
            "backgroundMode": raw_meta.get("backgroundMode") if raw_meta.get("backgroundMode") in ("neon-grid", "aurora", "mesh", "solid", "image") else "neon-grid",
            "density": raw_meta.get("density") if raw_meta.get("density") in ("compact", "comfortable") else "compact",
            "glow": clamp(raw_meta.get("glow"), 0, 100, 68),
            "surfaceOpacity": clamp(raw_meta.get("surfaceOpacity"), 45, 100, 82),
            "showLatency": raw_meta.get("showLatency", True) is True,
            "fullWidth": raw_meta.get("fullWidth", True) is True,
            "equalHeights": raw_meta.get("equalHeights", True) is True,
            "maxColumns": clamp(raw_meta.get("maxColumns"), 1, 6, 4),
        },
        "groups": [],
        "widgets": {
            "resources": raw.get("widgets", {}).get("resources", True) is True if isinstance(raw.get("widgets"), dict) else True,
            "dateTime": raw.get("widgets", {}).get("dateTime", True) is True if isinstance(raw.get("widgets"), dict) else True,
        },
    }
    pages: list[dict[str, str]] = []
    page_ids: set[str] = set()
    raw_pages = raw.get("pages") if isinstance(raw.get("pages"), list) else []
    for page_index, raw_page in enumerate(raw_pages[:20]):
        if not isinstance(raw_page, dict):
            continue
        page_id = text(raw_page.get("id"), 100, f"page-{page_index + 1}").strip() or f"page-{page_index + 1}"
        if page_id in page_ids:
            page_id = f"{page_id}-{page_index + 1}"
        page_ids.add(page_id)
        pages.append({"id": page_id, "name": text(raw_page.get("name"), 100, "Page").strip() or "Page"})
    if not pages:
        pages = [{"id": "home", "name": "Home"}]
        page_ids = {"home"}
    result["pages"] = pages
    default_page_id = pages[0]["id"]
    seen: set[str] = set()
    raw_groups = raw.get("groups") if isinstance(raw.get("groups"), list) else []
    for group_index, raw_group in enumerate(raw_groups[:100]):
        if not isinstance(raw_group, dict):
            continue
        group_id = text(raw_group.get("id"), 100, f"group-{group_index + 1}") or f"group-{group_index + 1}"
        if group_id in seen:
            group_id = f"{group_id}-{group_index + 1}"
        seen.add(group_id)
        group = {
            "id": group_id,
            "name": text(raw_group.get("name"), 100, "Group").strip() or "Group",
            "kind": raw_group.get("kind") if raw_group.get("kind") in ("services", "bookmarks") else "services",
            "columns": clamp(raw_group.get("columns"), 1, 6, 3),
            "collapsed": raw_group.get("collapsed", False) is True,
            "pageId": raw_group.get("pageId") if stored_version >= 6 and raw_group.get("pageId") in page_ids else default_page_id,
            "items": [],
        }
        raw_items = raw_group.get("items") if isinstance(raw_group.get("items"), list) else []
        for item_index, raw_item in enumerate(raw_items[:500]):
            if not isinstance(raw_item, dict):
                continue
            item_id = text(raw_item.get("id"), 100, f"item-{group_index + 1}-{item_index + 1}")
            while item_id in seen:
                item_id = f"{item_id}-{item_index + 2}"
            seen.add(item_id)
            item: dict[str, Any] = {
                "id": item_id,
                "name": text(raw_item.get("name"), 100, "Service").strip() or "Service",
                "href": text(raw_item.get("href"), 2000),
                "type": raw_item.get("type") if raw_item.get("type") in ("service", "bookmark") else "service",
                "statusStyle": raw_item.get("statusStyle") if raw_item.get("statusStyle") in ("dot", "badge", "none") else "dot",
            }
            if isinstance(raw_item.get("containerName"), str):
                item["containerName"] = text(raw_item["containerName"], 255)
            for key, limit in (("monitorUrl", 2000), ("description", 300), ("icon", 500)):
                if isinstance(raw_item.get(key), str):
                    item[key] = text(raw_item[key], limit)
            raw_widget = raw_item.get("widget")
            if isinstance(raw_widget, dict) and isinstance(raw_widget.get("type"), str):
                refs = raw_widget.get("secretRefs") if isinstance(raw_widget.get("secretRefs"), list) else []
                widget: dict[str, Any] = {
                    "type": text(raw_widget["type"], 80),
                    "secretRefs": [canonical_env_ref(ref) for ref in refs[:50] if isinstance(ref, str) and re.fullmatch(r"[A-Z][A-Z0-9_]*", ref)],
                }
                raw_bindings = raw_widget.get("secretBindings") if isinstance(raw_widget.get("secretBindings"), dict) else {}
                bindings = {
                    key.lower(): value
                    for key, value in list(raw_bindings.items())[:50]
                    if isinstance(key, str)
                    and re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]*", key)
                    and isinstance(value, str)
                    and canonical_env_ref(value) in widget["secretRefs"]
                }
                bindings = {key: canonical_env_ref(value) for key, value in bindings.items()}
                if bindings:
                    widget["secretBindings"] = bindings
                if isinstance(raw_widget.get("url"), str):
                    widget["url"] = text(raw_widget["url"], 2000)
                if isinstance(raw_widget.get("version"), (str, int)):
                    widget["version"] = raw_widget["version"]
                if widget["type"].lower() == "qbittorrent":
                    bindings = widget.setdefault("secretBindings", {})
                    for binding, ref in (
                        ("api_key", "RGDASH_QBITTORRENT_API_KEY"),
                        ("username", "RGDASH_QBITTORRENT_USERNAME"),
                        ("password", "RGDASH_QBITTORRENT_PASSWORD"),
                    ):
                        if ref not in widget["secretRefs"]:
                            widget["secretRefs"].append(ref)
                        bindings[binding] = ref
                item["widget"] = widget
            elif stored_version < 2:
                suggested = suggested_widget(item["name"], item.get("monitorUrl", ""))
                if suggested:
                    item["widget"] = suggested
            if not (stored_version < 3 and re.sub(r"[^a-z0-9]+", "", item["name"].lower()) == "homepage"):
                if stored_version < 7:
                    identity = re.sub(r"[^a-z0-9]+", "", item["name"].lower())
                    container_name = item.get("containerName", "")
                    if identity in ("rogueroutegpx", "rogueroutegpxweb") or container_name == "rogueroute-gpx-web":
                        item.update(
                            name="RogueRoute GPX",
                            containerName="rogueroute-gpx-web",
                            monitorUrl=ROGUEROUTE_WEB_HEALTH_URL,
                            description="Route generator",
                            icon="/icons/rogueroute-gpx.svg",
                        )
                        if ROGUEROUTE_PUBLIC_URL:
                            item["href"] = ROGUEROUTE_PUBLIC_URL
                    elif identity in ("roguerouteosrm", "rogueroutegpxosrm") or container_name == "rogueroute-gpx-osrm":
                        item.update(
                            name="RogueRoute OSRM",
                            containerName="rogueroute-gpx-osrm",
                            href="",
                            monitorUrl=ROGUEROUTE_OSRM_HEALTH_URL,
                            description="Local route engine",
                            icon="/icons/rogueroute-osrm.svg",
                        )
                    elif identity in ("rogueroutemanager", "rogueroutegpxmanager") or container_name == "rogueroute-gpx-manager":
                        item.update(
                            name="RogueRoute Manager",
                            containerName="rogueroute-gpx-manager",
                            href="",
                            monitorUrl=ROGUEROUTE_MANAGER_HEALTH_URL,
                            description="Private region manager",
                            icon="/icons/rogueroute-manager.svg",
                        )
                group["items"].append(item)
        result["groups"].append(group)
    result["groups"] = [group for group in result["groups"] if group["items"]]
    if not result["groups"]:
        result["groups"] = deepcopy(DEFAULT_DASHBOARD["groups"])
        for group in result["groups"]:
            group["pageId"] = default_page_id
    return result


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
              password_hash TEXT NOT NULL, salt TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
              token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              expires_at INTEGER NOT NULL, created_at TEXT, last_seen_at TEXT
            );
            CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);
            CREATE TABLE IF NOT EXISTS action_audit (
              id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL, username TEXT NOT NULL,
              action TEXT NOT NULL, target TEXT NOT NULL, outcome TEXT NOT NULL, detail TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS action_audit_time_idx ON action_audit(occurred_at DESC);
            """
        )
        session_columns = {row[1] for row in self.db.execute("PRAGMA table_info(sessions)")}
        if "created_at" not in session_columns:
            self.db.execute("ALTER TABLE sessions ADD COLUMN created_at TEXT")
        if "last_seen_at" not in session_columns:
            self.db.execute("ALTER TABLE sessions ADD COLUMN last_seen_at TEXT")
        now = utc_now()
        self.db.execute("UPDATE sessions SET created_at=COALESCE(created_at,?),last_seen_at=COALESCE(last_seen_at,?)", (now, now))
        self.db.commit()

    def setup_required(self) -> bool:
        with self.lock:
            return self.db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0

    def setup(self, username: str, password: str, dashboard: dict[str, Any]) -> tuple[str, int]:
        salt = secrets.token_bytes(16)
        password_hash = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=64)
        token, token_hash, expires = make_session()
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                if self.db.execute("SELECT COUNT(*) FROM users").fetchone()[0] != 0:
                    raise SetupCompleted("Setup has already been completed.")
                cursor = self.db.execute(
                    "INSERT INTO users(username,password_hash,salt,created_at) VALUES(?,?,?,?)",
                    (username, password_hash.hex(), salt.hex(), utc_now()),
                )
                self.db.execute(
                    "INSERT INTO settings(key,value,updated_at) VALUES('dashboard',?,?)",
                    (json.dumps(dashboard, separators=(",", ":")), utc_now()),
                )
                created_at = utc_now()
                self.db.execute(
                    "INSERT INTO sessions(token_hash,user_id,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?)",
                    (token_hash, cursor.lastrowid, expires, created_at, created_at),
                )
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
        return token, expires

    def login(self, username: str, password: str) -> tuple[str, int] | None:
        with self.lock:
            row = self.db.execute(
                "SELECT id,password_hash,salt FROM users WHERE username=?", (username,)
            ).fetchone()
        if not row:
            hashlib.scrypt(password.encode(), salt=b"0" * 16, n=2**14, r=8, p=1, dklen=64)
            return None
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(row[2]), n=2**14, r=8, p=1, dklen=64)
        if not hmac.compare_digest(actual.hex(), row[1]):
            return None
        token, token_hash, expires = make_session()
        with self.lock:
            self.db.execute("DELETE FROM sessions WHERE expires_at<?", (int(time.time()),))
            created_at = utc_now()
            self.db.execute(
                "INSERT INTO sessions(token_hash,user_id,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?)",
                (token_hash, row[0], expires, created_at, created_at),
            )
            self.db.commit()
        return token, expires

    def user_for_token(self, token: str | None) -> str | None:
        if not token:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.lock:
            row = self.db.execute(
                "SELECT users.username FROM sessions JOIN users ON users.id=sessions.user_id WHERE token_hash=? AND expires_at>?",
                (digest, int(time.time())),
            ).fetchone()
            if row:
                self.db.execute("UPDATE sessions SET last_seen_at=? WHERE token_hash=?", (utc_now(), digest))
                self.db.commit()
        return row[0] if row else None

    def logout(self, token: str | None) -> None:
        if not token:
            return
        with self.lock:
            self.db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
            self.db.commit()

    def sessions(self, current_token: str | None) -> list[dict[str, Any]]:
        current_hash = hashlib.sha256(current_token.encode()).hexdigest() if current_token else ""
        with self.lock:
            rows = self.db.execute(
                "SELECT token_hash,created_at,last_seen_at,expires_at FROM sessions WHERE expires_at>? ORDER BY last_seen_at DESC",
                (int(time.time()),),
            ).fetchall()
        return [
            {
                "id": row[0][:12],
                "createdAt": row[1],
                "lastSeenAt": row[2],
                "expiresAt": row[3],
                "current": hmac.compare_digest(row[0], current_hash),
            }
            for row in rows
        ]

    def revoke_session(self, session_id: str, current_token: str | None) -> bool:
        if not re.fullmatch(r"[0-9a-f]{12}", session_id):
            raise ValueError("Invalid session id")
        current_hash = hashlib.sha256(current_token.encode()).hexdigest() if current_token else ""
        with self.lock:
            cursor = self.db.execute(
                "DELETE FROM sessions WHERE token_hash LIKE ? AND token_hash<>?",
                (f"{session_id}%", current_hash),
            )
            self.db.commit()
        return cursor.rowcount > 0

    def audit(self, username: str, action: str, target: str, outcome: str, detail: str = "") -> None:
        with self.lock:
            self.db.execute(
                "INSERT INTO action_audit(occurred_at,username,action,target,outcome,detail) VALUES(?,?,?,?,?,?)",
                (utc_now(), text(username, 100), text(action, 100), text(target, 200), text(outcome, 40), text(detail, 500)),
            )
            self.db.execute(
                "DELETE FROM action_audit WHERE id NOT IN (SELECT id FROM action_audit ORDER BY id DESC LIMIT 1000)"
            )
            self.db.commit()

    def audit_entries(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.db.execute(
                "SELECT occurred_at,username,action,target,outcome,detail FROM action_audit ORDER BY id DESC LIMIT ?",
                (clamp(limit, 1, 250, 100),),
            ).fetchall()
        return [
            {"occurredAt": row[0], "username": row[1], "action": row[2], "target": row[3], "outcome": row[4], "detail": row[5]}
            for row in rows
        ]

    def dashboard(self) -> dict[str, Any]:
        with self.lock:
            row = self.db.execute("SELECT value FROM settings WHERE key='dashboard'").fetchone()
        if not row:
            return deepcopy(DEFAULT_DASHBOARD)
        try:
            return validate_dashboard(json.loads(row[0]))
        except (ValueError, json.JSONDecodeError):
            return deepcopy(DEFAULT_DASHBOARD)

    def save_dashboard(self, dashboard: dict[str, Any]) -> None:
        with self.lock:
            self.db.execute(
                "INSERT INTO settings(key,value,updated_at) VALUES('dashboard',?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                (json.dumps(dashboard, separators=(",", ":")), utc_now()),
            )
            self.db.commit()


def make_session() -> tuple[str, str, int]:
    token = secrets.token_urlsafe(32)
    return token, hashlib.sha256(token.encode()).hexdigest(), int(time.time()) + 14 * 24 * 3600


class UnixHTTPConnection(HTTPConnection):
    def __init__(self, socket_path: str):
        super().__init__("localhost", timeout=4)
        self.socket_path = socket_path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


def docker_request(path: str, maximum: int = 5_000_000) -> Any:
    connection = UnixHTTPConnection(DOCKER_SOCKET)
    try:
        connection.request("GET", path, headers={"Accept": "application/json"})
        response = connection.getresponse()
        if response.status >= 400:
            raise RuntimeError(f"Docker Engine returned HTTP {response.status}")
        return json.loads(response.read(maximum))
    finally:
        connection.close()


def docker_containers(include_stats: bool = False) -> list[dict[str, Any]]:
    raw = docker_request("/containers/json?all=1")
    containers = normalise_containers(raw)
    if include_stats:
        running = [item for item in containers if item["state"] == "running"][:100]
        with ThreadPoolExecutor(max_workers=8) as pool:
            snapshots = list(pool.map(docker_container_stats, [item["id"] for item in running]))
        for container, snapshot in zip(running, snapshots):
            container["stats"] = snapshot
    return containers


def normalise_container_stats(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"available": False}
    cpu = raw.get("cpu_stats") or {}
    previous_cpu = raw.get("precpu_stats") or {}
    cpu_delta = (cpu.get("cpu_usage") or {}).get("total_usage", 0) - (previous_cpu.get("cpu_usage") or {}).get("total_usage", 0)
    system_delta = cpu.get("system_cpu_usage", 0) - previous_cpu.get("system_cpu_usage", 0)
    online_cpus = cpu.get("online_cpus") or len((cpu.get("cpu_usage") or {}).get("percpu_usage") or []) or 1
    cpu_percent = max(0.0, cpu_delta / system_delta * online_cpus * 100) if system_delta > 0 and cpu_delta >= 0 else 0.0
    memory = raw.get("memory_stats") or {}
    cache = (memory.get("stats") or {}).get("inactive_file", (memory.get("stats") or {}).get("cache", 0))
    memory_used = max(0, int(memory.get("usage", 0)) - int(cache or 0))
    memory_limit = max(0, int(memory.get("limit", 0)))
    networks = raw.get("networks") or {}
    rx_bytes = sum(int(item.get("rx_bytes", 0)) for item in networks.values() if isinstance(item, dict)) if isinstance(networks, dict) else 0
    tx_bytes = sum(int(item.get("tx_bytes", 0)) for item in networks.values() if isinstance(item, dict)) if isinstance(networks, dict) else 0
    return {
        "available": True,
        "cpuPercent": round(cpu_percent, 1),
        "memoryUsed": memory_used,
        "memoryLimit": memory_limit,
        "networkRx": rx_bytes,
        "networkTx": tx_bytes,
    }


def docker_container_stats(container_id: str) -> dict[str, Any]:
    try:
        query = urlencode({"stream": "false", "one-shot": "true"})
        return normalise_container_stats(docker_request(f"/containers/{container_id}/stats?{query}", 2_000_000))
    except Exception:
        return {"available": False}


def normalise_containers(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise RuntimeError("Docker Engine returned an invalid container list")
    containers: list[dict[str, Any]] = []
    exact_labels = {"com.docker.compose.project", "com.docker.compose.service"}
    for container in raw:
        if not isinstance(container, dict):
            continue
        labels = {
            key: value
            for key, value in (container.get("Labels") or {}).items()
            if key in exact_labels or key.startswith("rogue.dashboard.")
        }
        state = str(container.get("State", "unknown"))
        status = str(container.get("Status", "unknown"))
        status_lower = status.lower()
        if "(healthy)" in status_lower:
            health = "healthy"
        elif "(unhealthy)" in status_lower:
            health = "unhealthy"
        elif "(health: starting)" in status_lower:
            health = "starting"
        elif state == "running":
            health = "none"
        else:
            health = "stopped"
        containers.append(
            {
                "id": str(container.get("Id", ""))[:12],
                "name": ((container.get("Names") or ["Unnamed container"])[0]).lstrip("/"),
                "image": container.get("Image", "unknown"),
                "state": state,
                "status": status,
                "health": health,
                "ports": [
                    {"privatePort": port.get("PrivatePort", 0), "publicPort": port.get("PublicPort"), "type": port.get("Type", "tcp")}
                    for port in container.get("Ports") or []
                ],
                "networks": sorted(
                    str(name)
                    for name in ((container.get("NetworkSettings") or {}).get("Networks") or {})
                    if name
                ),
                "labels": labels,
            }
        )
    return sorted(containers, key=lambda item: (item["state"] != "running", item["name"].lower()))


def docker_action(container_id: str, action: str) -> None:
    if not re.fullmatch(r"[0-9a-fA-F]{12,64}", container_id):
        raise ValueError("Invalid container id")
    if action not in ("start", "stop", "restart"):
        raise ValueError("Unsupported Docker action")
    protected = next(
        (
            item
            for item in docker_containers()
            if container_id.startswith(item["id"]) and item.get("labels", {}).get("rogue.dashboard.protected") == "true"
        ),
        None,
    )
    if protected:
        raise ValueError("Rogue Dashboard containers are protected from self-management")
    suffix = "?t=10" if action in ("stop", "restart") else ""
    connection = UnixHTTPConnection(DOCKER_SOCKET)
    try:
        connection.request("POST", f"/containers/{container_id}/{action}{suffix}", body=b"")
        response = connection.getresponse()
        response.read(100_000)
        if response.status >= 400:
            raise RuntimeError(f"Docker Engine returned HTTP {response.status}")
    finally:
        connection.close()


def containers_from_agent(include_stats: bool = False) -> list[dict[str, Any]]:
    if not DOCKER_AGENT_URL:
        return docker_containers(include_stats)
    suffix = "?stats=1" if include_stats else ""
    request = Request(
        f"{DOCKER_AGENT_URL.rstrip('/')}/containers{suffix}",
        headers={"Authorization": f"Bearer {DOCKER_AGENT_TOKEN}"},
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read(5_000_000))


def action_through_agent(container_id: str, action: str) -> None:
    if not DOCKER_AGENT_URL:
        docker_action(container_id, action)
        return
    request = Request(
        f"{DOCKER_AGENT_URL.rstrip('/')}/containers/{container_id}/{action}",
        method="POST",
        data=b"",
        headers={"Authorization": f"Bearer {DOCKER_AGENT_TOKEN}"},
    )
    with urlopen(request, timeout=15):
        return


def health_check(item: dict[str, Any], containers_by_name: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    checked_at = utc_now()
    url = item.get("monitorUrl", "")
    if not isinstance(url, str) or urlparse(url).scheme not in ("http", "https"):
        return {"itemId": item.get("id", ""), "state": "unknown", "checkedAt": checked_at}
    started = time.monotonic()
    status: int | None = None
    probe_error: str | None = None
    try:
        request = Request(url, method="HEAD", headers={"User-Agent": f"Rogue-Dashboard/{VERSION}"})
        with urlopen(request, timeout=4) as response:
            status = response.status
        probe_state = "online" if status < 500 else "offline"
    except HTTPError as error:
        status = error.code
        if status in (405, 501):
            try:
                request = Request(url, method="GET", headers={"User-Agent": f"Rogue-Dashboard/{VERSION}"})
                with urlopen(request, timeout=4) as response:
                    status = response.status
                probe_state = "online" if status < 500 else "offline"
            except HTTPError as get_error:
                status = get_error.code
                probe_state = "online" if status < 500 else "offline"
            except (URLError, TimeoutError, ValueError):
                status = None
                probe_state = "offline"
                probe_error = "Private endpoint is unreachable from the dashboard network"
        else:
            probe_state = "online" if status < 500 else "offline"
    except (URLError, TimeoutError, ValueError):
        probe_state = "offline"
        probe_error = "Private endpoint is unreachable from the dashboard network"

    container_name = item.get("containerName", "")
    container = (containers_by_name or {}).get(container_name) if isinstance(container_name, str) else None
    container_state = container.get("state") if container else None
    container_health = container.get("health") if container else None
    if container_state and container_state != "running":
        state = "offline"
        message = f"Container is {container_state}"
        source = "docker"
    elif container_health == "unhealthy":
        state = "offline"
        message = "Docker health check is failing"
        source = "docker"
    elif container_health == "starting":
        state = "unknown"
        message = "Docker health check is still starting"
        source = "docker"
    elif probe_state == "offline" and status is not None:
        state = "offline"
        message = f"Health endpoint returned HTTP {status}"
        source = "endpoint"
    elif container_health == "healthy":
        state = "online"
        message = "Container healthy and endpoint responding" if probe_state == "online" else "Container healthy; private endpoint is not reachable from the dashboard network"
        source = "docker+endpoint" if probe_state == "online" else "docker"
    else:
        state = probe_state
        message = "Endpoint responding" if probe_state == "online" else probe_error or "Endpoint is offline"
        source = "endpoint"
    result: dict[str, Any] = {
        "itemId": item.get("id", ""),
        "state": state,
        "source": source,
        "message": message,
        "probeState": probe_state,
        "latencyMs": round((time.monotonic() - started) * 1000),
        "checkedAt": checked_at,
    }
    if container_state:
        result["containerState"] = container_state
    if container_health:
        result["containerHealth"] = container_health
    if probe_error:
        result["probeError"] = probe_error
    if status is not None:
        result["status"] = status
    return result


def system_stats() -> dict[str, Any]:
    memory_total = memory_available = 0
    try:
        values = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            values[key] = int(value.strip().split()[0]) * 1024
        memory_total = values.get("MemTotal", 0)
        memory_available = values.get("MemAvailable", 0)
    except (OSError, ValueError):
        pass
    try:
        uptime = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError):
        uptime = 0
    try:
        containers = containers_from_agent()
        running_containers = sum(item.get("state") == "running" for item in containers)
        total_containers = len(containers)
        docker_status = "ok"
    except Exception:
        running_containers = None
        total_containers = None
        docker_status = "unavailable"
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0
    return {
        "uptimeSeconds": round(uptime),
        "memoryUsed": max(0, memory_total - memory_available),
        "memoryTotal": memory_total,
        "load": load,
        "cpuCount": os.cpu_count() or 1,
        "runningContainers": running_containers,
        "totalContainers": total_containers,
        "dockerStatus": docker_status,
    }


FAILED_LOGINS: dict[str, tuple[int, float]] = {}
LOGIN_LOCK = threading.Lock()
HEALTH_CACHE: tuple[float, list[dict[str, Any]]] = (0, [])
HEALTH_LOCK = threading.Lock()
WIDGET_CACHE: tuple[float, list[dict[str, Any]]] = (0, [])
WIDGET_LOCK = threading.Lock()
DB: Database | None = None


def clear_monitor_caches() -> None:
    global HEALTH_CACHE, WIDGET_CACHE
    with HEALTH_LOCK:
        HEALTH_CACHE = (0, [])
    with WIDGET_LOCK:
        WIDGET_CACHE = (0, [])


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "RogueDashboard"

    def log_message(self, format_string: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format_string % args}")

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("X-Permitted-Cross-Domain-Policies", "none")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'",
        )
        if self.request_is_secure():
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        super().end_headers()

    def json_response(self, value: Any, status: int = 200, cookie: str | None = None) -> None:
        payload = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(payload)

    def body_json(self) -> Any:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid content length") from error
        if length < 1 or length > MAX_BODY:
            raise ValueError("Request body is empty or too large")
        if "application/json" not in self.headers.get("Content-Type", ""):
            raise ValueError("Content-Type must be application/json")
        return json.loads(self.rfile.read(length))

    def session_token(self) -> str | None:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        return cookie[SESSION_COOKIE].value if SESSION_COOKIE in cookie else None

    def request_host(self) -> str:
        supplied = self.headers.get("Host", "").strip()
        if supplied.startswith("[") and "]" in supplied:
            return supplied[1 : supplied.index("]")].lower().rstrip(".")
        return supplied.rsplit(":", 1)[0].lower().rstrip(".")

    def request_is_secure(self) -> bool:
        if SECURE_COOKIES:
            return True
        if not TRUST_PROXY_HEADERS:
            return False
        forwarded = self.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip().lower()
        return forwarded == "https"

    def require_allowed_host(self) -> bool:
        if not CONFIGURED_ALLOWED_HOSTS or self.request_host() in ALLOWED_HOSTS:
            return True
        self.json_response(
            {"error": "This host is not allowed. Add it to RGDASH_ALLOWED_HOSTS and restart Rogue Dashboard."},
            HTTPStatus.MISDIRECTED_REQUEST,
        )
        return False

    def username(self) -> str | None:
        return DB.user_for_token(self.session_token()) if DB else None

    def require_admin(self) -> bool:
        if self.username():
            return True
        self.json_response({"error": "Sign in to change the dashboard."}, HTTPStatus.UNAUTHORIZED)
        return False

    def do_GET(self) -> None:
        if not self.require_allowed_host():
            return
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/ping":
            self.json_response({"ok": True, "version": VERSION})
        elif path == "/api/bootstrap":
            username = self.username()
            self.json_response(
                {
                    "version": VERSION,
                    "setupRequired": DB.setup_required(),
                    "authenticated": bool(username),
                    "username": username,
                    "dashboard": DB.dashboard() if not DB.setup_required() else deepcopy(DEFAULT_DASHBOARD),
                    "proxy": {
                        "requestHost": self.request_host(),
                        "secure": self.request_is_secure(),
                        "trustedHeaders": TRUST_PROXY_HEADERS,
                    },
                    "serviceUrls": {"rogueRoute": ROGUEROUTE_PUBLIC_URL},
                }
            )
        elif path == "/api/dashboard":
            if DB.setup_required():
                self.json_response({"error": "Complete setup first."}, HTTPStatus.NOT_FOUND)
            else:
                self.json_response(DB.dashboard())
        elif path == "/api/system":
            self.json_response(system_stats())
        elif path == "/api/health":
            global HEALTH_CACHE
            with HEALTH_LOCK:
                if HEALTH_CACHE[0] > time.time():
                    results = HEALTH_CACHE[1]
                else:
                    items = [item for group in DB.dashboard()["groups"] for item in group["items"] if item.get("monitorUrl")]
                    try:
                        containers_by_name = {container["name"]: container for container in containers_from_agent()}
                    except Exception:
                        containers_by_name = {}
                    with ThreadPoolExecutor(max_workers=8) as pool:
                        results = list(pool.map(lambda item: health_check(item, containers_by_name), items))
                    HEALTH_CACHE = (time.time() + 15, results)
            self.json_response(results)
        elif path == "/api/widgets":
            global WIDGET_CACHE
            with WIDGET_LOCK:
                if WIDGET_CACHE[0] > time.time():
                    widget_results = WIDGET_CACHE[1]
                else:
                    widget_items = [
                        item
                        for group in DB.dashboard()["groups"]
                        for item in group["items"]
                        if isinstance(item.get("widget"), dict)
                    ]
                    with ThreadPoolExecutor(max_workers=6) as pool:
                        widget_results = list(pool.map(collect_widget, widget_items))
                    checked_at = utc_now()
                    for result in widget_results:
                        result["checkedAt"] = checked_at
                    WIDGET_CACHE = (time.time() + 25, widget_results)
            self.json_response({"supported": sorted(SUPPORTED_WIDGETS), "widgets": widget_results})
        elif path == "/api/docker/containers":
            if not self.require_admin():
                return
            try:
                self.json_response({"containers": containers_from_agent(include_stats=True)})
            except Exception as error:
                self.json_response({"containers": [], "error": str(error)}, HTTPStatus.SERVICE_UNAVAILABLE)
        elif path == "/api/admin/sessions":
            if not self.require_admin():
                return
            self.json_response({"sessions": DB.sessions(self.session_token())})
        elif path == "/api/admin/audit":
            if not self.require_admin():
                return
            self.json_response({"entries": DB.audit_entries()})
        elif path.startswith("/api/"):
            self.json_response({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        elif path.startswith("/custom/"):
            self.serve_custom(path)
        else:
            self.serve_static(path)

    def do_HEAD(self) -> None:
        if not self.require_allowed_host():
            return
        path = urlparse(self.path).path
        if path == "/api/ping":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
        elif path.startswith("/api/"):
            self.send_response(HTTPStatus.NOT_FOUND)
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif path.startswith("/custom/"):
            self.serve_custom(path, head_only=True)
        else:
            self.serve_static(path, head_only=True)

    def do_POST(self) -> None:
        if not self.require_allowed_host():
            return
        path = urlparse(self.path).path
        try:
            body = self.body_json()
            if path == "/api/setup":
                self.complete_setup(body)
            elif path == "/api/auth/login":
                self.login(body)
            elif path == "/api/auth/logout":
                token = self.session_token()
                username = self.username() or "administrator"
                DB.logout(token)
                DB.audit(username, "auth.logout", "session", "success")
                self.json_response({"ok": True}, cookie=clear_cookie(self.request_is_secure()))
            elif path == "/api/import/homepage":
                if not DB.setup_required() and not self.require_admin():
                    return
                self.json_response(import_homepage(read_import_files(body)))
            elif path == "/api/import/dashboard":
                if not DB.setup_required() and not self.require_admin():
                    return
                if not isinstance(body, dict) or "dashboard" not in body:
                    raise ValueError("A Rogue Dashboard JSON object is required")
                imported_dashboard = validate_dashboard(body["dashboard"])
                imported_items = [item for group in imported_dashboard["groups"] for item in group["items"]]
                self.json_response({
                    "dashboard": imported_dashboard,
                    "warnings": [],
                    "summary": {
                        "groups": len(imported_dashboard["groups"]),
                        "services": sum(item["type"] == "service" for item in imported_items),
                        "bookmarks": sum(item["type"] == "bookmark" for item in imported_items),
                        "widgets": sum(isinstance(item.get("widget"), dict) for item in imported_items),
                        "secretReferences": sorted({ref for item in imported_items for ref in item.get("widget", {}).get("secretRefs", [])}),
                    },
                })
            elif path == "/api/monitor/refresh":
                if not self.require_admin():
                    return
                clear_monitor_caches()
                self.json_response({"ok": True})
            elif path == "/api/docker/action":
                if not self.require_admin():
                    return
                if not isinstance(body, dict):
                    raise ValueError("Invalid Docker action request")
                container_id = text(body.get("containerId"), 64)
                action = text(body.get("action"), 20)
                username = self.username() or "administrator"
                try:
                    action_through_agent(container_id, action)
                    DB.audit(username, f"docker.{action}", container_id[:12], "success")
                except Exception as error:
                    DB.audit(username, f"docker.{action or 'unknown'}", container_id[:12], "failed", type(error).__name__)
                    raise
                self.json_response({"ok": True, "containerId": container_id, "action": action})
            elif path == "/api/admin/sessions/revoke":
                if not self.require_admin():
                    return
                if not isinstance(body, dict):
                    raise ValueError("Invalid session request")
                session_id = text(body.get("sessionId"), 12)
                revoked = DB.revoke_session(session_id, self.session_token())
                DB.audit(self.username() or "administrator", "session.revoke", session_id, "success" if revoked else "not_found")
                self.json_response({"ok": True, "revoked": revoked})
            else:
                self.json_response({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except (ValueError, json.JSONDecodeError, zipfile.BadZipFile) as error:
            self.json_response({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except SetupCompleted as error:
            self.json_response({"error": str(error)}, HTTPStatus.CONFLICT)
        except sqlite3.IntegrityError:
            self.json_response({"error": "That username is already in use."}, HTTPStatus.CONFLICT)
        except (HTTPError, URLError, RuntimeError, TimeoutError) as error:
            self.json_response({"error": f"Docker action failed: {error}"}, HTTPStatus.SERVICE_UNAVAILABLE)

    def do_PUT(self) -> None:
        if not self.require_allowed_host():
            return
        if urlparse(self.path).path != "/api/dashboard":
            self.json_response({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        if not self.require_admin():
            return
        try:
            dashboard = validate_dashboard(self.body_json())
            DB.save_dashboard(dashboard)
            DB.audit(self.username() or "administrator", "dashboard.save", "dashboard", "success")
            clear_monitor_caches()
            self.json_response({"ok": True, "dashboard": dashboard})
        except (ValueError, json.JSONDecodeError) as error:
            self.json_response({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def complete_setup(self, body: Any) -> None:
        if not DB.setup_required():
            self.json_response({"error": "Setup has already been completed."}, HTTPStatus.CONFLICT)
            return
        if not isinstance(body, dict):
            raise ValueError("Invalid setup request")
        username = text(body.get("username"), 50).strip()
        password = body.get("password")
        if len(username) < 2:
            raise ValueError("Username must contain at least 2 characters")
        if not isinstance(password, str) or not 10 <= len(password) <= 200:
            raise ValueError("Password must contain between 10 and 200 characters")
        dashboard = validate_dashboard(body.get("dashboard"))
        token, expires = DB.setup(username, password, dashboard)
        DB.audit(username, "setup.complete", "dashboard", "success")
        self.json_response({"ok": True}, HTTPStatus.CREATED, session_cookie(token, expires, self.request_is_secure()))

    def login(self, body: Any) -> None:
        if not isinstance(body, dict):
            raise ValueError("Invalid login request")
        client = self.client_address[0]
        now = time.time()
        with LOGIN_LOCK:
            attempts, reset = FAILED_LOGINS.get(client, (0, now + 900))
            if reset <= now:
                attempts, reset = 0, now + 900
            if attempts >= 5:
                self.json_response({"error": "Too many attempts. Please wait 15 minutes."}, HTTPStatus.TOO_MANY_REQUESTS)
                return
        username = text(body.get("username"), 50).strip()
        password = body.get("password") if isinstance(body.get("password"), str) else ""
        result = DB.login(username, password)
        if not result:
            with LOGIN_LOCK:
                FAILED_LOGINS[client] = (attempts + 1, reset)
            self.json_response({"error": "The username or password is incorrect."}, HTTPStatus.UNAUTHORIZED)
            return
        with LOGIN_LOCK:
            FAILED_LOGINS.pop(client, None)
        DB.audit(username, "auth.login", "session", "success")
        self.json_response(
            {"ok": True, "username": username},
            cookie=session_cookie(*result, secure=self.request_is_secure()),
        )

    def serve_static(self, requested_path: str, head_only: bool = False) -> None:
        relative = requested_path.lstrip("/") or "index.html"
        candidate = (STATIC_DIR / relative).resolve()
        static_root = STATIC_DIR.resolve()
        if static_root not in candidate.parents and candidate != static_root:
            self.json_response({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            if Path(relative).suffix:
                self.json_response({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return
            candidate = STATIC_DIR / "index.html"
        payload = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache" if candidate.name == "index.html" else "public, max-age=3600")
        self.end_headers()
        if not head_only:
            self.wfile.write(payload)

    def serve_custom(self, requested_path: str, head_only: bool = False) -> None:
        relative = requested_path.removeprefix("/custom/")
        candidate = (CUSTOM_DIR / relative).resolve()
        custom_root = CUSTOM_DIR.resolve()
        if (custom_root not in candidate.parents and candidate != custom_root) or not candidate.is_file():
            self.json_response({"error": "Custom asset not found"}, HTTPStatus.NOT_FOUND)
            return
        if candidate.suffix.lower() not in CUSTOM_ASSET_SUFFIXES:
            self.json_response({"error": "Custom asset type is not supported"}, HTTPStatus.NOT_FOUND)
            return
        if candidate.stat().st_size > MAX_CUSTOM_ASSET:
            self.json_response({"error": "Custom asset exceeds the 10 MB safety limit"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        payload = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        if not head_only:
            self.wfile.write(payload)


def session_cookie(token: str, expires: int, secure: bool = False) -> str:
    secure_attribute = "; Secure" if secure else ""
    return f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={max(0, expires-int(time.time()))}{secure_attribute}"


def clear_cookie(secure: bool = False) -> str:
    secure_attribute = "; Secure" if secure else ""
    return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0{secure_attribute}"


def read_import_files(body: Any) -> dict[str, str]:
    if not isinstance(body, dict):
        raise ValueError("Invalid import request")
    result: dict[str, str] = {}
    allowed = {"services.yaml", "services.yml", "bookmarks.yaml", "bookmarks.yml", "settings.yaml", "settings.yml", "widgets.yaml", "widgets.yml"}
    if isinstance(body.get("files"), dict):
        for name, value in body["files"].items():
            base = Path(str(name)).name.lower()
            if base in allowed and isinstance(value, str):
                result[base] = value
    if isinstance(body.get("zipBase64"), str):
        try:
            archive_bytes = base64.b64decode(body["zipBase64"], validate=True)
        except ValueError as error:
            raise ValueError("The ZIP upload is not valid base64") from error
        if len(archive_bytes) > MAX_BODY:
            raise ValueError("The ZIP upload exceeds 2 MB")
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_ENTRIES:
                raise ValueError(f"The ZIP upload contains more than {MAX_ARCHIVE_ENTRIES} entries")
            total_uncompressed = 0
            for info in entries:
                base = Path(info.filename).name.lower()
                if base not in allowed or info.is_dir():
                    continue
                if info.flag_bits & 0x1:
                    raise ValueError("Encrypted ZIP files are not supported")
                if info.file_size > 1_000_000:
                    raise ValueError(f"{base} exceeds the 1 MB safety limit")
                total_uncompressed += info.file_size
                if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED:
                    raise ValueError("The ZIP upload expands beyond the 5 MB safety limit")
                result[base] = archive.read(info).decode("utf-8")
    if not result:
        raise ValueError("No supported legacy dashboard YAML files were found")
    return result


class AgentHandler(BaseHTTPRequestHandler):
    server_version = "RogueDockerAgent"

    def log_message(self, format_string: str, *args: Any) -> None:
        print(f"agent - {format_string % args}")

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self.respond({"ok": True})
            elif parsed.path == "/containers":
                if not self.authorized():
                    return
                include_stats = parse_qs(parsed.query).get("stats") == ["1"]
                self.respond(docker_containers(True) if include_stats else docker_containers())
            else:
                self.respond({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except Exception as error:
            self.respond({"error": str(error)}, HTTPStatus.SERVICE_UNAVAILABLE)

    def do_POST(self) -> None:
        try:
            if not self.authorized():
                return
            match = re.fullmatch(r"/containers/([0-9a-fA-F]{12,64})/(start|stop|restart)", self.path)
            if not match:
                self.respond({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return
            docker_action(match.group(1), match.group(2))
            self.respond({"ok": True})
        except ValueError as error:
            self.respond({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:
            self.respond({"error": str(error)}, HTTPStatus.SERVICE_UNAVAILABLE)

    def authorized(self) -> bool:
        expected = f"Bearer {DOCKER_AGENT_TOKEN}"
        supplied = self.headers.get("Authorization", "")
        if DOCKER_AGENT_TOKEN and hmac.compare_digest(supplied, expected):
            return True
        self.respond({"error": "Unauthorized"}, HTTPStatus.UNAUTHORIZED)
        return False

    def respond(self, value: Any, status: int = 200) -> None:
        payload = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)


def healthcheck() -> int:
    try:
        target = os.environ.get("HEALTHCHECK_URL", f"http://127.0.0.1:{PORT}/api/ping")
        with urlopen(target, timeout=3) as response:
            return 0 if response.status == 200 else 1
    except Exception:
        return 1


def main() -> int:
    global DB
    command = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if command == "healthcheck":
        return healthcheck()
    if command == "agent":
        if not DOCKER_AGENT_TOKEN:
            print("DOCKER_AGENT_TOKEN is required", file=sys.stderr)
            return 1
        server = ThreadingHTTPServer(("0.0.0.0", AGENT_PORT), AgentHandler)
        print(f"Rogue Dashboard Docker metadata agent listening on {AGENT_PORT}")
    else:
        if DOCKER_AGENT_URL and not DOCKER_AGENT_TOKEN:
            print("DOCKER_AGENT_TOKEN is required when using the Docker metadata agent", file=sys.stderr)
            return 1
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        DB = Database(DATA_DIR / "rogue-dashboard.sqlite")
        server = ThreadingHTTPServer(("0.0.0.0", PORT), DashboardHandler)
        print(f"Rogue Dashboard {VERSION} listening on {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
