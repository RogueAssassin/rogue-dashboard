# Rogue Dashboard

Rogue Dashboard is a self-hosted dashboard built specifically to run as a Docker Compose stack. The host does not need a web-development workspace, package manager, database server or manually installed runtime.

Current release: **0.4.2**

The application uses one small container image for two isolated services:

- `dashboard` serves the browser interface, authentication, legacy configuration importer, SQLite data and health checks.
- `docker-agent` is an internal-only companion that exposes an allow-listed set of Docker operations.

## Current port

Rogue Dashboard now owns the former Homepage slot on host port **7805**:

```yaml
ports:
  - "7805:8080"
```

Change only the left-hand number if a different host port is needed, then recreate the dashboard service.

## Install on WSL Docker

```bash
chmod +x install.sh
./install.sh
```

The installer:

1. Confirms Docker and Docker Compose are available.
2. Creates the local `.env` file.
3. Detects the WSL user and Docker socket group IDs.
4. Generates a private token between the dashboard and Docker agent.
5. Creates the persistent `data` and `custom` asset directories.
6. Safely migrates any legacy environment names to `RGDASH_*`.
7. Creates or joins `media-net` so service discovery and Nginx proxying are always available.
8. Builds and starts the two Docker services.

Open `http://localhost:7805` and follow the setup screen. The supplied legacy configuration ZIP can be selected directly; it imports 5 organised groups, 12 services, 3 branded links and 10 safe environment references. The old Homepage card is omitted.

## Upgrade an existing installation

Do **not** delete the existing `rogue-dashboard` folder. Its `.env`, `data/` and `custom/` content hold your credentials, administrator account, imported layout and local assets.

From the directory that contains your existing `rogue-dashboard` folder:

```bash
unzip -o rogue-dashboard-v0.4.2-proxy-connections.zip
cd rogue-dashboard
chmod +x upgrade.sh
./upgrade.sh
```

The release ZIP intentionally contains neither `.env` nor `data/`, so extracting it over the existing folder does not overwrite saved information. The upgrade script builds while the current dashboard stays online, backs up `data/`, `.env` and custom assets, migrates legacy environment names, stops Homepage when it owns port 7805, and validates the replacement container. A failed takeover restores the previous dashboard on port 8000 and restarts Homepage.

Never use `docker compose down -v` for an upgrade. This project currently uses a bind-mounted data directory rather than a named volume, but avoiding `-v` is the safe habit for future releases too.

See [docs/RELEASE_0.4.2.md](docs/RELEASE_0.4.2.md) for the connection and reverse-proxy checklist.

## Features included

- Visual first-run setup and legacy ZIP/YAML import.
- Add, edit, delete and drag service or bookmark cards.
- Rename groups and choose responsive column counts.
- Search, themes, colour and optional background customisation.
- Local administrator authentication and SQLite persistence.
- Service health checks from inside the Docker network.
- Docker container discovery and running-container counts.
- Confirmed start, stop and restart controls for administrators.
- JSON dashboard backup export.
- Live qBittorrent, Prowlarr, Radarr, Sonarr, Seerr, Bazarr, Tautulli and Pi-hole metrics.
- Widget readiness diagnostics that identify missing environment references without exposing their values.
- Responsive desktop, tablet and mobile interface.
- Thoughtful Neon default plus Midnight, Graphite, Ocean, Ember and Daylight presets.
- Neon grid, aurora, mesh, solid and custom-image backgrounds with adjustable glow and opacity.
- Compact operations layout with full metric blocks and response-time badges.
- Local bundled service icons and a persistent custom icon/background folder.
- Connection Centre covering container reachability, API authentication and missing configuration.
- Verified `.env` loading indicators for each integration without displaying values.
- qBittorrent WebUI username/password authentication with the required session cookie.
- Working Appearance, Layout, Connect and Docker customisation tabs.
- Horizontal GitHub → RogueGaming → Thoughtful Comms menu with local icons.
- Guided live-integration setup from the card editor.
- No cloud account, analytics, telemetry or subscription service.

## Docker commands

```bash
# Status
docker compose -f docker-compose.yaml ps

# Logs
docker compose -f docker-compose.yaml logs -f

# Rebuild after changing application files
docker compose -f docker-compose.yaml up -d --build

# Stop while preserving dashboard data
docker compose -f docker-compose.yaml down
```

The primary Compose file joins `media-net` directly. The old override remains only for compatibility with earlier scripts.

## Data and backups

Persistent application data is stored under:

```text
./data/rogue-dashboard.sqlite
```

`upgrade.sh` automatically backs up the complete `data` directory, `.env` and existing `custom` assets under `./backups/YYYYMMDD-HHMMSS/` while the stack is stopped. Dashboard layouts can also be exported as JSON from the visual editor.

## Credentials

Imported literal passwords, tokens and API keys are discarded. Rogue Dashboard 0.4 uses `RGDASH_*` environment names while the real values remain in `.env`. During upgrade, `migrate-env.sh` converts `HOMEPAGE_VAR_*` and other `HOMEPAGE_*` entries without printing or changing their values, and keeps `.env.pre-rgdash` as a private fallback copy. Never commit or share either file.

Examples:

```text
RGDASH_QBITTORRENT_USERNAME=
RGDASH_QBITTORRENT_PASSWORD=
RGDASH_RADARR_KEY=
RGDASH_SEERR_KEY=
RGDASH_PIHOLE_KEY=
```

## Local icons and backgrounds

Docker has no standard image-label field that reliably provides an application logo. Rogue Dashboard therefore includes local icons for the recognised services and falls back to initials for unknown services.

To add your own files:

1. Copy an SVG or transparent PNG to `custom/icons/`.
2. Open **Customise → edit the card**.
3. Enter `/custom/icons/your-icon.svg` in **Icon URL or local path**.

For a local background, copy the image to `custom/backgrounds/`, enter `/custom/backgrounds/your-background.jpg` in Appearance settings, and choose **Custom image**. These files are bind-mounted read-only into the container and persist across image rebuilds.

## Connection checks

Open **Admin → Customise → Connect**, then select **Test now**. Each integration reports private reachability, API authentication and the exact `RGDASH_*` names loaded from `.env`—never their values. DNS errors specifically identify a missing `media-net` attachment, while refused-port and credential errors remain separate.

Set `RGDASH_QBITTORRENT_USERNAME` and `RGDASH_QBITTORRENT_PASSWORD` to the WebUI login. Version 0.4.2 migrates the incorrectly named 0.4.1 qBittorrent value into the password field and assumes the default `admin` username only when no username exists. Radarr uses the complete 32-character `RGDASH_RADARR_KEY` with its private `http://radarr:7878` address.

For Nginx Proxy Manager, create `dash.roguegaming.com.au` with scheme `http`, forward hostname `rogue-dashboard` and forward port `8080`. Do not use `localhost`, the host port `7805`, HTTPS to the container, or the old Homepage target. Enable Websockets, Force SSL and HTTP/2. If Cloudflare Tunnel fronts Nginx Proxy Manager, its published application service is `http://nginx-proxy-manager:80`.

## Security

The main dashboard does not mount the Docker socket. Only the internal agent receives it, and that agent accepts container listing plus start, stop and restart—not shell execution, image deletion, arbitrary Engine paths or Compose file changes. Requests require a private generated token and Docker actions additionally require an administrator session.

See [docs/SECURITY.md](docs/SECURITY.md) for deployment guidance.
