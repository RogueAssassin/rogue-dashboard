from __future__ import annotations

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import dashboard as dashboard_app
from importer import import_homepage
from integrations import collect_widget


class WidgetFixtureHandler(BaseHTTPRequestHandler):
    requested_paths = []
    posted_paths = []

    def log_message(self, *_args):
        return

    def respond(self, value, status=200, headers=None):
        payload = value.encode() if isinstance(value, str) else json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain" if isinstance(value, str) else "application/json")
        self.send_header("Content-Length", str(len(payload)))
        for key, header_value in (headers or {}).items():
            self.send_header(key, header_value)
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        type(self).posted_paths.append(urlparse(self.path).path)
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.path == "/api/v2/auth/login":
            values = parse_qs(body.decode())
            origin = f"http://{self.headers.get('Host')}"
            if values == {"username": ["widget-user"], "password": ["widget-pass"]} and self.headers.get("Origin") == origin and self.headers.get("Referer") == f"{origin}/":
                self.respond("Ok.", headers={"Set-Cookie": "SID=test-session; Path=/; HttpOnly"})
            else:
                self.respond("Fails.", 403)
        elif self.path == "/api/auth" and json.loads(body) == {"password": "pihole-pass"}:
            self.respond({"session": {"valid": True, "sid": "pihole-session", "csrf": "unused"}})
        else:
            self.respond({"error": "not found"}, 404)

    def do_DELETE(self):
        if self.path == "/api/auth" and self.headers.get("X-FTL-SID") == "pihole-session":
            self.respond({}, 200)
        else:
            self.respond({"error": "not found"}, 404)

    def do_GET(self):
        parsed = urlparse(self.path)
        type(self).requested_paths.append(parsed.path)
        api_authorization = self.headers.get("Authorization", "")
        qbit_api_path = parsed.path in ("/api/v2/transfer/info", "/api/v2/torrents/info")
        if qbit_api_path and api_authorization.startswith("Bearer ") and api_authorization != f"Bearer qbt_{'A' * 28}":
            self.respond({"error": "unauthorized"}, 401)
            return
        qbit_authorized = "SID=test-session" in self.headers.get("Cookie", "") or api_authorization == f"Bearer qbt_{'A' * 28}"
        if parsed.path == "/api/v2/transfer/info" and qbit_authorized:
            self.respond({"dl_info_speed": 2_000_000, "up_info_speed": 500_000})
        elif parsed.path == "/api/v2/torrents/info" and qbit_authorized:
            self.respond([{"state": "downloading"}, {"state": "uploading"}, {"state": "pausedUP"}])
        elif parsed.path == "/api/v3/queue" and self.headers.get("X-Api-Key") in ("arr-key", "a" * 32):
            self.respond({"totalRecords": 4, "records": []})
        elif parsed.path == "/api/v3/health" and self.headers.get("X-Api-Key") == "arr-key":
            self.respond([{"type": "warning"}])
        elif parsed.path == "/api/v3/wanted/cutoff" and self.headers.get("X-Api-Key") == "a" * 32:
            self.respond({"totalRecords": 1, "records": []})
        elif parsed.path == "/api/v3/wanted/missing" and self.headers.get("X-Api-Key") in ("arr-key", "a" * 32):
            self.respond({"totalRecords": 2, "records": []})
        elif parsed.path == "/api/v3/movie" and self.headers.get("X-Api-Key") == "a" * 32:
            self.respond([{"id": 1}, {"id": 2}, {"id": 3}])
        elif parsed.path == "/api/v3/series" and self.headers.get("X-Api-Key") == "arr-key":
            self.respond([{"id": 1}, {"id": 2}])
        elif parsed.path == "/api/v1/indexer" and self.headers.get("X-Api-Key") == "prowlarr-key":
            self.respond([{"enable": True}, {"enable": False}, {"enable": True}])
        elif parsed.path == "/api/v1/health" and self.headers.get("X-Api-Key") == "prowlarr-key":
            self.respond([])
        elif parsed.path == "/api/v1/indexerstats" and self.headers.get("X-Api-Key") == "prowlarr-key":
            self.respond({"indexers": [{"numberOfGrabs": 8, "numberOfQueries": 12, "numberOfFailedGrabs": 1, "numberOfFailedQueries": 2}]})
        elif parsed.path == "/api/v2" and parse_qs(parsed.query) == {"apikey": ["tautulli-key"], "cmd": ["get_activity"]}:
            self.respond({"response": {"result": "success", "data": {"stream_count": "3", "stream_count_transcode": "1", "total_bandwidth": 12000}}})
        elif parsed.path == "/api/episodes/wanted" and self.headers.get("X-API-KEY") == "bazarr-key":
            self.respond({"total": 7, "data": []})
        elif parsed.path == "/api/movies/wanted" and self.headers.get("X-API-KEY") == "bazarr-key":
            self.respond({"total": 2, "data": []})
        elif parsed.path == "/api/stats/summary" and self.headers.get("X-FTL-SID") == "pihole-session":
            self.respond({"queries": {"total": 1000, "blocked": 245, "percent_blocked": 24.5}, "clients": {"active": 9}, "gravity": {"domains_being_blocked": 123456}})
        elif parsed.path == "/api/v1/request/count" and self.headers.get("X-Api-Key") == "seerr-key":
            self.respond({"pending": 2, "approved": 3, "processing": 1, "available": 7})
        else:
            self.respond({"error": "not found"}, 404)


class RogueDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = ROOT / "tests" / "fixtures" / "homepage"
        cls.files = {path.name: path.read_text() for path in fixture.glob("*.yaml")}

    def test_imports_generic_homepage_configuration(self):
        result = import_homepage(self.files)
        self.assertEqual(result["summary"]["groups"], 7)
        self.assertEqual(result["summary"]["services"], 12)
        self.assertEqual(result["summary"]["bookmarks"], 3)
        self.assertEqual(result["summary"]["widgets"], 2)
        self.assertEqual(len(result["summary"]["secretReferences"]), 10)
        self.assertEqual(result["dashboard"]["meta"]["title"], "Home Lab Dashboard")
        qbit = result["dashboard"]["groups"][0]["items"][0]["widget"]
        self.assertEqual(qbit["secretBindings"]["api_key"], "RGDASH_QBITTORRENT_API_KEY")
        self.assertEqual(qbit["secretBindings"]["username"], "RGDASH_QBITTORRENT_USERNAME")
        self.assertEqual(qbit["secretBindings"]["password"], "RGDASH_QBITTORRENT_PASSWORD")
        self.assertNotIn("Homepage", [item["name"] for group in result["dashboard"]["groups"] for item in group["items"]])
        bookmarks = [
            item["name"]
            for group in result["dashboard"]["groups"]
            if group["kind"] == "bookmarks"
            for item in group["items"]
        ]
        self.assertEqual(bookmarks, ["GitHub", "Docker Docs", "Project Website"])

    def test_discards_literal_widget_credentials(self):
        result = import_homepage({
            "services.yaml": "- Services:\n    - Example:\n        widget:\n          type: example\n          password: never-store-this\n"
        })
        self.assertNotIn("never-store-this", json.dumps(result["dashboard"]))
        self.assertIn("literal password value was discarded", result["warnings"][0])

    def test_live_service_widget_collectors_keep_secrets_server_side(self):
        WidgetFixtureHandler.requested_paths = []
        WidgetFixtureHandler.posted_paths = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), WidgetFixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        values = {
            "RGDASH_QBITTORRENT_API_KEY": f"qbt_{'A' * 28}",
            "RGDASH_QBITTORRENT_USERNAME": "widget-user",
            "RGDASH_QBITTORRENT_PASSWORD": "widget-pass",
            "RGDASH_RADARR_KEY": "a" * 32,
            "TEST_ARR_KEY": "arr-key",
            "TEST_PROWLARR_KEY": "prowlarr-key",
            "TEST_TAUTULLI_KEY": "tautulli-key",
            "TEST_BAZARR_KEY": "bazarr-key",
            "TEST_PIHOLE_KEY": "pihole-pass",
            "TEST_SEERR_KEY": "seerr-key",
        }
        previous = {key: os.environ.get(key) for key in values}
        os.environ.update(values)
        try:
            cases = [
                ("qbittorrent", ["RGDASH_QBITTORRENT_API_KEY", "RGDASH_QBITTORRENT_USERNAME", "RGDASH_QBITTORRENT_PASSWORD"], {"api_key": "RGDASH_QBITTORRENT_API_KEY", "username": "RGDASH_QBITTORRENT_USERNAME", "password": "RGDASH_QBITTORRENT_PASSWORD"}, ["Download", "Upload", "Leech", "Seed"]),
                ("radarr", ["RGDASH_RADARR_KEY"], {"key": "RGDASH_RADARR_KEY"}, ["Wanted", "Missing", "Queued", "Movies"]),
                ("sonarr", ["TEST_ARR_KEY"], {"key": "TEST_ARR_KEY"}, ["Wanted", "Queued", "Series"]),
                ("prowlarr", ["TEST_PROWLARR_KEY"], {"key": "TEST_PROWLARR_KEY"}, ["Grabs", "Queries", "Fail grabs", "Fail queries"]),
                ("seerr", ["TEST_SEERR_KEY"], {"key": "TEST_SEERR_KEY"}, ["Pending", "Approved", "Processing", "Available"]),
                ("tautulli", ["TEST_TAUTULLI_KEY"], {"key": "TEST_TAUTULLI_KEY"}, ["Playing", "Transcoding", "Bitrate"]),
                ("bazarr", ["TEST_BAZARR_KEY"], {"key": "TEST_BAZARR_KEY"}, ["Missing episodes", "Missing movies"]),
                ("pihole", ["TEST_PIHOLE_KEY"], {"key": "TEST_PIHOLE_KEY"}, ["Queries", "Blocked", "Gravity", "Clients"]),
            ]
            for index, (kind, refs, bindings, labels) in enumerate(cases):
                item = {"id": f"widget-{index}", "widget": {"type": kind, "url": base, "secretRefs": refs, "secretBindings": bindings}}
                result = collect_widget(item)
                self.assertEqual(result["state"], "ok", result)
                self.assertEqual([metric["label"] for metric in result["metrics"]], labels)
                self.assertTrue(all(entry["loaded"] for entry in result["environment"]))
                serialized = json.dumps(result)
                for secret in values.values():
                    self.assertNotIn(secret, serialized)
            self.assertEqual(WidgetFixtureHandler.requested_paths.count("/api/v2/torrents/info"), 1)
            self.assertEqual(WidgetFixtureHandler.posted_paths.count("/api/v2/auth/login"), 0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_qbittorrent_falls_back_when_api_key_is_rejected(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), WidgetFixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        values = {
            "RGDASH_QBITTORRENT_API_KEY": f"qbt_{'B' * 28}",
            "RGDASH_QBITTORRENT_USERNAME": "widget-user",
            "RGDASH_QBITTORRENT_PASSWORD": "widget-pass",
        }
        previous = {key: os.environ.get(key) for key in values}
        os.environ.update(values)
        WidgetFixtureHandler.posted_paths = []
        try:
            result = collect_widget({
                "id": "qbittorrent",
                "widget": {
                    "type": "qbittorrent",
                    "url": f"http://127.0.0.1:{server.server_port}",
                    "secretRefs": list(values),
                    "secretBindings": {
                        "api_key": "RGDASH_QBITTORRENT_API_KEY",
                        "username": "RGDASH_QBITTORRENT_USERNAME",
                        "password": "RGDASH_QBITTORRENT_PASSWORD",
                    },
                },
            })
            self.assertEqual(result["state"], "ok", result)
            self.assertEqual(result["authentication"], "username_password_fallback")
            self.assertIn("API key was rejected", result["message"])
            self.assertEqual(WidgetFixtureHandler.posted_paths.count("/api/v2/auth/login"), 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_widget_reports_missing_environment_reference(self):
        os.environ.pop("TEST_MISSING_WIDGET_KEY", None)
        result = collect_widget({
            "id": "radarr",
            "widget": {"type": "radarr", "url": "http://radarr:7878", "secretRefs": ["TEST_MISSING_WIDGET_KEY"]},
        })
        self.assertEqual(result["state"], "configuration_required")
        self.assertEqual(result["missingRefs"], ["TEST_MISSING_WIDGET_KEY"])

    def test_radarr_reports_incomplete_api_key_before_connecting(self):
        previous = os.environ.get("RGDASH_RADARR_KEY")
        os.environ["RGDASH_RADARR_KEY"] = "incomplete-key"
        try:
            result = collect_widget({
                "id": "radarr",
                "widget": {
                    "type": "radarr",
                    "url": "http://radarr:7878",
                    "secretRefs": ["RGDASH_RADARR_KEY"],
                    "secretBindings": {"key": "RGDASH_RADARR_KEY"},
                },
            })
            self.assertEqual(result["state"], "error")
            self.assertIn("32-character", result["message"])
        finally:
            if previous is None:
                os.environ.pop("RGDASH_RADARR_KEY", None)
            else:
                os.environ["RGDASH_RADARR_KEY"] = previous

    def test_v03_dashboard_migrates_to_neon_and_rgdash_references(self):
        legacy = import_homepage(self.files)["dashboard"]
        legacy["version"] = 1
        legacy["meta"]["theme"] = "midnight"
        next(item for item in legacy["groups"][0]["items"] if item["name"] == "Seerr").pop("widget", None)
        widget = legacy["groups"][0]["items"][0]["widget"]
        widget["secretRefs"] = ["HOMEPAGE_VAR_QBITTORRENT_USERNAME", "HOMEPAGE_VAR_QBITTORRENT_PASSWORD"]
        widget["secretBindings"] = {"username": "HOMEPAGE_VAR_QBITTORRENT_USERNAME", "password": "HOMEPAGE_VAR_QBITTORRENT_PASSWORD"}
        migrated = dashboard_app.validate_dashboard(legacy)
        self.assertEqual(migrated["version"], 5)
        self.assertEqual(migrated["meta"]["theme"], "neon")
        self.assertEqual(migrated["meta"]["density"], "compact")
        migrated_widget = migrated["groups"][0]["items"][0]["widget"]
        self.assertEqual(migrated_widget["secretBindings"]["api_key"], "RGDASH_QBITTORRENT_API_KEY")
        self.assertEqual(migrated_widget["secretBindings"]["username"], "RGDASH_QBITTORRENT_USERNAME")
        seerr = next(item for item in migrated["groups"][0]["items"] if item["name"] == "Seerr")
        self.assertEqual(seerr["widget"]["type"], "seerr")
        self.assertEqual(seerr["widget"]["secretRefs"], ["RGDASH_SEERR_KEY"])

    def test_v04_dashboard_removes_legacy_homepage_card_without_reordering_bookmarks(self):
        current = import_homepage(self.files)["dashboard"]
        current["groups"].append({
            "id": "admin", "name": "Admin", "kind": "services", "columns": 2, "collapsed": False,
            "items": [{"id": "homepage", "name": "Homepage", "href": "http://homepage:3000", "type": "service", "statusStyle": "dot"}],
        })
        current["version"] = 2
        migrated = dashboard_app.validate_dashboard(current)
        names = [item["name"] for group in migrated["groups"] for item in group["items"]]
        self.assertNotIn("Homepage", names)
        bookmark_groups = [group["name"] for group in migrated["groups"] if group["kind"] == "bookmarks"]
        self.assertEqual(bookmark_groups, ["Developer resources", "Documentation", "Project"])

    def test_v05_migrates_rogueroute_cards_to_private_health_endpoints(self):
        current = {
            "version": 3,
            "meta": {"title": "Docker"},
            "groups": [{
                "id": "routes", "name": "Routes", "kind": "services", "columns": 3, "items": [
                    {"id": "web", "name": "RogueRoute-GPX", "href": "http://old", "type": "service"},
                    {"id": "osrm", "name": "rogueroute-osrm", "href": "http://old", "type": "service"},
                    {"id": "manager", "name": "rogueroute-gpx-manager", "href": "http://old", "type": "service"},
                ],
            }],
        }
        with patch.object(dashboard_app, "ROGUEROUTE_PUBLIC_URL", "https://gpx.example.com"):
            migrated = dashboard_app.validate_dashboard(current)
        web, osrm, manager = migrated["groups"][0]["items"]
        self.assertEqual(web["href"], "https://gpx.example.com")
        self.assertEqual(web["monitorUrl"], "http://rogueroute-gpx-web:9080/api/health")
        self.assertEqual(osrm["href"], "")
        self.assertEqual(osrm["monitorUrl"], "http://rogueroute-gpx-osrm:5000/")
        self.assertEqual(manager["href"], "")
        self.assertEqual(manager["monitorUrl"], "http://rogueroute-gpx-manager:9090/health")
        self.assertTrue(all(item["icon"].startswith("/icons/rogueroute-") for item in (web, osrm, manager)))
        self.assertEqual(
            [item["containerName"] for item in (web, osrm, manager)],
            ["rogueroute-gpx-web", "rogueroute-gpx-osrm", "rogueroute-gpx-manager"],
        )

    def test_docker_container_summary_includes_networks_and_stable_order(self):
        raw = [
            {
                "Id": "b" * 64,
                "Names": ["/stopped"],
                "Image": "example/stopped:latest",
                "State": "exited",
                "Status": "Exited (0)",
                "Ports": [],
                "Labels": {},
                "NetworkSettings": {"Networks": {"media-net": {}}},
            },
            {
                "Id": "a" * 64,
                "Names": ["/running"],
                "Image": "example/running:latest",
                "State": "running",
                "Status": "Up 1 minute",
                "Ports": [{"PrivatePort": 9080, "PublicPort": 9080, "Type": "tcp"}],
                "Labels": {"com.docker.compose.project": "routes", "unrelated.secret": "discard"},
                "NetworkSettings": {"Networks": {"rogueroute-gpx": {}, "media-net": {}}},
            },
        ]
        containers = dashboard_app.normalise_containers(raw)
        self.assertEqual([item["name"] for item in containers], ["running", "stopped"])
        self.assertEqual(containers[0]["networks"], ["media-net", "rogueroute-gpx"])
        self.assertNotIn("unrelated.secret", containers[0]["labels"])

    def test_system_stats_reports_running_and_total_containers(self):
        containers = [{"state": "running"}, {"state": "running"}, {"state": "exited"}]
        with patch.object(dashboard_app, "containers_from_agent", return_value=containers):
            stats = dashboard_app.system_stats()
        self.assertEqual(stats["runningContainers"], 2)
        self.assertEqual(stats["totalContainers"], 3)
        self.assertEqual(stats["dockerStatus"], "ok")

    def test_reads_homepage_zip_without_extracting_paths(self):
        archive = BytesIO()
        with ZipFile(archive, "w") as output:
            output.writestr("config/services.yaml", self.files["services.yaml"])
            output.writestr("../../ignored.txt", "not imported")
        files = dashboard_app.read_import_files({"zipBase64": base64.b64encode(archive.getvalue()).decode()})
        self.assertIn("services.yaml", files)
        self.assertNotIn("ignored.txt", files)

    def test_rejects_zip_entry_and_expansion_bombs(self):
        too_many = BytesIO()
        with ZipFile(too_many, "w", ZIP_DEFLATED) as output:
            for index in range(dashboard_app.MAX_ARCHIVE_ENTRIES + 1):
                output.writestr(f"ignored-{index}.txt", "")
        with self.assertRaisesRegex(ValueError, "more than"):
            dashboard_app.read_import_files({"zipBase64": base64.b64encode(too_many.getvalue()).decode()})

        expanded = BytesIO()
        with ZipFile(expanded, "w", ZIP_DEFLATED) as output:
            for index in range(6):
                output.writestr(f"folder-{index}/services.yaml", "A" * 900_000)
        with self.assertRaisesRegex(ValueError, "expands beyond"):
            dashboard_app.read_import_files({"zipBase64": base64.b64encode(expanded.getvalue()).decode()})

    def test_database_authentication_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            database = dashboard_app.Database(Path(directory) / "dashboard.sqlite")
            self.assertTrue(database.setup_required())
            imported = import_homepage(self.files)["dashboard"]
            token, _ = database.setup("admin", "a-secure-test-password", imported)
            with self.assertRaises(dashboard_app.SetupCompleted):
                database.setup("second-admin", "another-secure-password", imported)
            self.assertEqual(database.user_for_token(token), "admin")
            self.assertIsNone(database.login("admin", "incorrect-password"))
            self.assertIsNotNone(database.login("admin", "a-secure-test-password"))
            self.assertEqual(database.dashboard()["meta"]["title"], "Home Lab Dashboard")

    def test_setup_and_authenticated_save_over_http(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = dashboard_app.DB
            previous_custom = dashboard_app.CUSTOM_DIR
            dashboard_app.DB = dashboard_app.Database(Path(directory) / "api.sqlite")
            dashboard_app.CUSTOM_DIR = Path(directory) / "custom"
            (dashboard_app.CUSTOM_DIR / "icons").mkdir(parents=True)
            (dashboard_app.CUSTOM_DIR / "icons" / "example.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
            (dashboard_app.CUSTOM_DIR / "icons" / "blocked.html").write_text("<script>alert(1)</script>")
            server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard_app.DashboardHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(f"{base}/api/bootstrap") as response:
                    bootstrap = json.load(response)
                    self.assertTrue(bootstrap["setupRequired"])
                    self.assertEqual(bootstrap["version"], dashboard_app.VERSION)
                    self.assertEqual(response.headers["Cross-Origin-Opener-Policy"], "same-origin")
                imported = import_homepage(self.files)["dashboard"]
                request = Request(
                    f"{base}/api/setup",
                    method="POST",
                    data=json.dumps({"username": "admin", "password": "a-secure-test-password", "dashboard": imported}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(request) as response:
                    cookie = response.headers["Set-Cookie"].split(";", 1)[0]
                    self.assertEqual(response.status, 201)
                with urlopen(f"{base}/custom/icons/example.svg") as response:
                    self.assertEqual(response.headers.get_content_type(), "image/svg+xml")
                with urlopen(f"{base}/favicon.svg") as response:
                    self.assertEqual(response.headers.get_content_type(), "image/svg+xml")
                for name in ("rogueroute-gpx.svg", "rogueroute-osrm.svg", "rogueroute-manager.svg"):
                    with urlopen(f"{base}/icons/{name}") as response:
                        self.assertEqual(response.headers.get_content_type(), "image/svg+xml")
                with self.assertRaises(HTTPError) as context:
                    urlopen(f"{base}/custom/../not-allowed.svg")
                self.assertEqual(context.exception.code, 404)
                with self.assertRaises(HTTPError) as context:
                    urlopen(f"{base}/custom/icons/blocked.html")
                self.assertEqual(context.exception.code, 404)
                with self.assertRaises(HTTPError) as context:
                    urlopen(f"{base}/missing-script.js")
                self.assertEqual(context.exception.code, 404)
                imported["meta"]["title"] = "Updated dashboard"
                request = Request(
                    f"{base}/api/dashboard",
                    method="PUT",
                    data=json.dumps(imported).encode(),
                    headers={"Content-Type": "application/json", "Cookie": cookie},
                )
                with urlopen(request) as response:
                    self.assertEqual(json.load(response)["dashboard"]["meta"]["title"], "Updated dashboard")
                dashboard_app.WIDGET_CACHE = (0, [])
                with urlopen(f"{base}/api/widgets") as response:
                    widgets = json.load(response)
                    self.assertIn("qbittorrent", widgets["supported"])
                    self.assertIn("seerr", widgets["supported"])
                    self.assertEqual(len(widgets["widgets"]), 8)
                    self.assertTrue(all(item["state"] == "configuration_required" for item in widgets["widgets"]))
                dashboard_app.HEALTH_CACHE = (9999999999, [{"old": True}])
                dashboard_app.WIDGET_CACHE = (9999999999, [{"old": True}])
                unauthenticated = Request(
                    f"{base}/api/monitor/refresh",
                    method="POST",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                )
                with self.assertRaises(HTTPError) as context:
                    urlopen(unauthenticated)
                self.assertEqual(context.exception.code, 401)
                authenticated = Request(
                    f"{base}/api/monitor/refresh",
                    method="POST",
                    data=b"{}",
                    headers={"Content-Type": "application/json", "Cookie": cookie},
                )
                with urlopen(authenticated) as response:
                    self.assertTrue(json.load(response)["ok"])
                self.assertEqual(dashboard_app.HEALTH_CACHE, (0, []))
                self.assertEqual(dashboard_app.WIDGET_CACHE, (0, []))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
                dashboard_app.DB = previous
                dashboard_app.CUSTOM_DIR = previous_custom

    def test_environment_migration_preserves_values_and_canonical_names(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "HOMEPAGE_VAR_RADARR_KEY=secret-a=b\n"
                "HOMEPAGE_VAR_CF_KEY=secret-cf\n"
                "RGDASH_RADARR_KEY=canonical-wins\n"
                "RGDASH_QBITTORRENT_API_KEY=qbt_1234567890123456789012345678\n"
                "TZ=Australia/Melbourne\n"
            )
            result = subprocess.run(
                ["sh", str(ROOT / "migrate-env.sh"), str(env_file)],
                check=True,
                capture_output=True,
                text=True,
            )
            migrated = env_file.read_text()
            self.assertNotIn("HOMEPAGE_", migrated)
            self.assertIn("RGDASH_RADARR_KEY=canonical-wins", migrated)
            self.assertIn("RGDASH_CF_KEY=secret-cf", migrated)
            self.assertIn("RGDASH_QBITTORRENT_API_KEY=qbt_1234567890123456789012345678", migrated)
            self.assertNotIn("RGDASH_QBITTORRENT_USERNAME=", migrated)
            self.assertNotIn("RGDASH_QBITTORRENT_PASSWORD=", migrated)
            self.assertIn("TZ=Australia/Melbourne", migrated)
            self.assertNotIn("secret-a", result.stdout)
            self.assertEqual((Path(f"{env_file}.pre-rgdash")).read_text().splitlines()[0], "HOMEPAGE_VAR_RADARR_KEY=secret-a=b")

    def test_agent_requires_private_token(self):
        previous_token = dashboard_app.DOCKER_AGENT_TOKEN
        previous_list = dashboard_app.docker_containers
        previous_action = dashboard_app.docker_action
        actions = []
        dashboard_app.DOCKER_AGENT_TOKEN = "test-agent-token"
        dashboard_app.docker_containers = lambda: []
        dashboard_app.docker_action = lambda container_id, action: actions.append((container_id, action))
        server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard_app.AgentHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/containers"
        try:
            with self.assertRaises(HTTPError) as context:
                urlopen(url)
            self.assertEqual(context.exception.code, 401)
            request = Request(url, headers={"Authorization": "Bearer test-agent-token"})
            with urlopen(request) as response:
                self.assertEqual(json.load(response), [])
            request = Request(
                f"http://127.0.0.1:{server.server_port}/containers/0123456789ab/restart",
                method="POST",
                data=b"",
                headers={"Authorization": "Bearer test-agent-token"},
            )
            with urlopen(request) as response:
                self.assertTrue(json.load(response)["ok"])
            self.assertEqual(actions, [("0123456789ab", "restart")])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            dashboard_app.DOCKER_AGENT_TOKEN = previous_token
            dashboard_app.docker_containers = previous_list
            dashboard_app.docker_action = previous_action


if __name__ == "__main__":
    unittest.main()
