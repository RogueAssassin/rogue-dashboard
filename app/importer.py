from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from homepage_yaml import loads


DEFAULT_DASHBOARD = {
    "version": 3,
    "meta": {
        "title": "My Docker Dashboard",
        "subtitle": "Everything running at home, in one friendly place",
        "theme": "neon",
        "accent": "#ff2bd6",
        "accentSecondary": "#00e5ff",
        "background": "",
        "backgroundMode": "neon-grid",
        "density": "compact",
        "glow": 68,
        "surfaceOpacity": 82,
        "showLatency": True,
        "fullWidth": True,
        "equalHeights": True,
        "maxColumns": 4,
    },
    "groups": [
        {"id": "favourites", "name": "Favourites", "kind": "services", "columns": 3, "collapsed": False, "items": []}
    ],
    "widgets": {"resources": True, "dateTime": True},
}

SENSITIVE = {"apikey", "api_key", "authorization", "clientsecret", "client_secret", "key", "password", "secret", "token", "username"}
REFERENCE = re.compile(r"\{\{\s*([A-Z][A-Z0-9_]*)\s*}}|\$\{\s*([A-Z][A-Z0-9_]*)\s*}")

INTEGRATION_DEFAULTS = {
    "qbittorrent": (
        "qbittorrent",
        ["RGDASH_QBITTORRENT_USERNAME", "RGDASH_QBITTORRENT_PASSWORD"],
        {
            "username": "RGDASH_QBITTORRENT_USERNAME",
            "password": "RGDASH_QBITTORRENT_PASSWORD",
        },
    ),
    "prowlarr": ("prowlarr", ["RGDASH_PROWLARR_KEY"], {"key": "RGDASH_PROWLARR_KEY"}),
    "radarr": ("radarr", ["RGDASH_RADARR_KEY"], {"key": "RGDASH_RADARR_KEY"}),
    "sonarr": ("sonarr", ["RGDASH_SONARR_KEY"], {"key": "RGDASH_SONARR_KEY"}),
    "seerr": ("seerr", ["RGDASH_SEERR_KEY"], {"key": "RGDASH_SEERR_KEY"}),
    "jellyseerr": ("seerr", ["RGDASH_SEERR_KEY"], {"key": "RGDASH_SEERR_KEY"}),
    "overseerr": ("seerr", ["RGDASH_SEERR_KEY"], {"key": "RGDASH_SEERR_KEY"}),
    "bazarr": ("bazarr", ["RGDASH_BAZARR_KEY"], {"key": "RGDASH_BAZARR_KEY"}),
    "tautulli": ("tautulli", ["RGDASH_TAUTULLI_KEY"], {"key": "RGDASH_TAUTULLI_KEY"}),
    "pihole": ("pihole", ["RGDASH_PIHOLE_KEY"], {"key": "RGDASH_PIHOLE_KEY"}),
}


def _canonical_reference(value: str) -> str:
    if value.startswith("HOMEPAGE_VAR_"):
        return f"RGDASH_{value.removeprefix('HOMEPAGE_VAR_')}"
    if value.startswith("HOMEPAGE_"):
        return f"RGDASH_{value.removeprefix('HOMEPAGE_')}"
    return value


def suggested_widget(name: str, url: str) -> dict[str, Any] | None:
    key = re.sub(r"[^a-z0-9]+", "", name.lower())
    configured = INTEGRATION_DEFAULTS.get(key)
    if not configured or not url:
        return None
    kind, refs, bindings = configured
    result: dict[str, Any] = {
        "type": kind,
        "url": url,
        "secretRefs": list(refs),
        "secretBindings": dict(bindings),
    }
    if kind == "pihole":
        result["version"] = 6
    return result


def organize_branded_links(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    brands: dict[str, dict[str, Any]] = {}
    result: list[dict[str, Any]] = []
    definitions = {
        "github": ("GitHub", "/icons/github.svg"),
        "roguegaming": ("RogueGaming", "/icons/roguegaming.svg"),
        "thoughtfulcomms": ("Thoughtful Comms", "/icons/thoughtful-comms.svg"),
    }
    for group in groups:
        kept: list[dict[str, Any]] = []
        for item in group.get("items", []):
            if group.get("kind") != "bookmarks":
                kept.append(item)
                continue
            identity = re.sub(r"[^a-z0-9]+", "", f"{item.get('name', '')} {item.get('href', '')}".lower())
            brand = next((key for key in definitions if key in identity), None)
            if not brand:
                kept.append(item)
                continue
            if brand not in brands:
                name, icon = definitions[brand]
                item = dict(item)
                item.update(name=name, icon=icon, type="bookmark", statusStyle="none")
                brands[brand] = item
        if kept:
            copied = dict(group)
            copied["items"] = kept
            result.append(copied)
    ordered = [brands[key] for key in ("github", "roguegaming", "thoughtfulcomms") if key in brands]
    if ordered:
        result.append({
            "id": "branded-links",
            "name": "Links",
            "kind": "bookmarks",
            "columns": 3,
            "collapsed": False,
            "items": ordered,
        })
    return result


def _slug(name: str, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "item"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _references(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return sorted({_canonical_reference(match.group(1) or match.group(2)) for match in REFERENCE.finditer(value)})


def _widget(raw: Any, warnings: list[str], item_name: str) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("type"), str):
        return None
    refs: set[str] = set()
    bindings: dict[str, str] = {}
    for key, value in raw.items():
        if key.lower() not in SENSITIVE:
            continue
        found = _references(value)
        refs.update(found)
        if len(found) == 1:
            bindings[key.lower()] = found[0]
        if value not in (None, "") and not found:
            warnings.append(f"{item_name}: a literal {key} value was discarded; move it to an environment variable.")
    result: dict[str, Any] = {"type": raw["type"], "secretRefs": sorted(refs)}
    if bindings:
        result["secretBindings"] = bindings
    if raw["type"].lower() == "qbittorrent":
        result["secretRefs"] = [ref for ref in result["secretRefs"] if ref != "RGDASH_QBITTORRENT_API_KEY"]
        for binding, ref in (
            ("username", "RGDASH_QBITTORRENT_USERNAME"),
            ("password", "RGDASH_QBITTORRENT_PASSWORD"),
        ):
            if ref not in result["secretRefs"]:
                result["secretRefs"].append(ref)
            result.setdefault("secretBindings", {})[binding] = ref
        result.get("secretBindings", {}).pop("api_key", None)
    if isinstance(raw.get("url"), str):
        result["url"] = raw["url"]
    if isinstance(raw.get("version"), (str, int)):
        result["version"] = raw["version"]
    return result


def _item(name: str, raw: Any, kind: str, used: set[str], warnings: list[str]) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    result: dict[str, Any] = {
        "id": _slug(name, used),
        "name": name,
        "href": source.get("href", "") if isinstance(source.get("href", ""), str) else "",
        "type": "bookmark" if kind == "bookmarks" else "service",
        "statusStyle": source.get("statusStyle") if source.get("statusStyle") in ("dot", "badge", "none") else "dot",
    }
    for source_key, target_key in (("siteMonitor", "monitorUrl"), ("description", "description"), ("icon", "icon")):
        if isinstance(source.get(source_key), str):
            result[target_key] = source[source_key]
    widget = _widget(source.get("widget"), warnings, name)
    if widget:
        result["widget"] = widget
    elif kind == "services":
        suggested = suggested_widget(name, result.get("monitorUrl", ""))
        if suggested:
            result["widget"] = suggested
    return result


def _groups(raw: Any, kind: str, layout: dict[str, Any], used: set[str], warnings: list[str]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    result: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        for group_name, raw_items in entry.items():
            if not isinstance(raw_items, list):
                continue
            items: list[dict[str, Any]] = []
            for raw_item in raw_items:
                if not isinstance(raw_item, dict):
                    continue
                for name, value in raw_item.items():
                    if kind == "services" and re.sub(r"[^a-z0-9]+", "", str(name).lower()) == "homepage":
                        continue
                    bookmark_value = value[0] if isinstance(value, list) and value and isinstance(value[0], dict) else value
                    items.append(_item(str(name), bookmark_value, kind, used, warnings))
            layout_entry = layout.get(group_name, {}) if isinstance(layout.get(group_name), dict) else {}
            columns = layout_entry.get("columns", 2 if kind == "bookmarks" else 3)
            if not isinstance(columns, int):
                columns = 3
            result.append({
                "id": _slug(str(group_name), used),
                "name": str(group_name),
                "kind": kind,
                "columns": max(1, min(6, columns)),
                "collapsed": False,
                "items": items,
            })
    return result


def import_homepage(files: dict[str, str]) -> dict[str, Any]:
    warnings: list[str] = []

    def parse(name: str) -> Any:
        text = files.get(name) or files.get(name.replace(".yaml", ".yml"))
        if not text:
            return None
        try:
            return loads(text)
        except ValueError as error:
            warnings.append(f"{name} could not be parsed: {error}")
            return None

    services = parse("services.yaml")
    bookmarks = parse("bookmarks.yaml")
    settings = parse("settings.yaml")
    widgets = parse("widgets.yaml")
    settings = settings if isinstance(settings, dict) else {}
    layout = settings.get("layout") if isinstance(settings.get("layout"), dict) else {}
    used: set[str] = set()
    groups = organize_branded_links(
        _groups(services, "services", layout, used, warnings) + _groups(bookmarks, "bookmarks", layout, used, warnings)
    )
    dashboard = deepcopy(DEFAULT_DASHBOARD)
    dashboard["groups"] = groups or dashboard["groups"]
    if isinstance(settings.get("title"), str):
        dashboard["meta"]["title"] = settings["title"]
    dashboard["meta"]["theme"] = "light" if settings.get("theme") == "light" else "neon"
    if isinstance(settings.get("fullWidth"), bool):
        dashboard["meta"]["fullWidth"] = settings["fullWidth"]
    if isinstance(settings.get("useEqualHeights"), bool):
        dashboard["meta"]["equalHeights"] = settings["useEqualHeights"]
    if isinstance(settings.get("maxGroupColumns"), int):
        dashboard["meta"]["maxColumns"] = max(1, min(6, settings["maxGroupColumns"]))
    widget_names = {next(iter(entry)) for entry in widgets or [] if isinstance(entry, dict) and entry}
    dashboard["widgets"] = {"resources": "resources" in widget_names, "dateTime": "datetime" in widget_names}
    items = [item for group in groups for item in group["items"]]
    refs = sorted({ref for item in items for ref in item.get("widget", {}).get("secretRefs", [])})
    return {
        "dashboard": dashboard,
        "warnings": warnings,
        "summary": {
            "groups": len(groups),
            "services": sum(item["type"] == "service" for item in items),
            "bookmarks": sum(item["type"] == "bookmark" for item in items),
            "widgets": len(widget_names),
            "secretReferences": refs,
        },
    }
