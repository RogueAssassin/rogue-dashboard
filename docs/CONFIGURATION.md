# Configuration reference

Rogue Dashboard reads runtime values from `.env` through Docker Compose. Restart the dashboard after changing them:

```bash
docker compose up -d --force-recreate dashboard
```

## Core values

| Variable | Default | Purpose |
| --- | --- | --- |
| `TZ` | `Etc/UTC` | Container timezone. Use an IANA name such as `Europe/London`. |
| `RGDASH_PORT` | `7805` | Host port published for the browser. |
| `RGDASH_BACKUP_KEEP` | `0` | Successful upgrade backups to retain. `0` disables automatic pruning. |
| `RGDASH_IMAGE` | `ghcr.io/rogueassassin/rogue-dashboard:latest` | Optional release tag or digest pin. |
| `PUID` / `PGID` | `1000` | Host user and group used for persistent files. |
| `DOCKER_GID` | `999` | Group ID of `/var/run/docker.sock`; the installer detects it. |
| `DOCKER_AGENT_TOKEN` | generated | Private dashboard-to-agent credential. Do not share it. |
| `MEDIA_NETWORK` | `media-net` | External Docker network shared with apps and a proxy. |
| `RGDASH_EXTRA_NETWORK` | empty | Optional second existing application network attached only to the dashboard. Install and upgrade auto-select `rogueroute-gpx` when it already exists and this value is empty. |
| `RGDASH_ROGUEROUTE_URL` | empty | Optional public URL for a discovered RogueRoute GPX Web card. |
| `SECURE_COOKIES` | `false` | Force Secure session cookies. Use `true` behind HTTPS when required. |
| `RGDASH_TRUST_PROXY_HEADERS` | `true` | Honour forwarded protocol information from a trusted proxy path. |
| `RGDASH_ALLOWED_HOSTS` | empty | Optional comma-separated host header allowlist. |

## Service credentials

| Integration | Environment variable | Usual private URL |
| --- | --- | --- |
| qBittorrent 5.2+ | `RGDASH_QBITTORRENT_API_KEY` | `http://qbittorrent:8080` or your configured WebUI port |
| qBittorrent fallback | `RGDASH_QBITTORRENT_USERNAME`, `RGDASH_QBITTORRENT_PASSWORD` | same as above |
| Prowlarr | `RGDASH_PROWLARR_KEY` | `http://prowlarr:9696` |
| Radarr | `RGDASH_RADARR_KEY` | `http://radarr:7878` |
| Sonarr | `RGDASH_SONARR_KEY` | `http://sonarr:8989` |
| Seerr | `RGDASH_SEERR_KEY` | `http://seerr:5055` |
| Bazarr | `RGDASH_BAZARR_KEY` | `http://bazarr:6767` |
| Tautulli | `RGDASH_TAUTULLI_KEY` | `http://tautulli:8181` |
| Pi-hole | `RGDASH_PIHOLE_KEY` | the Pi-hole HTTP address on the shared network |

Private URLs are examples, not enforced defaults. Use the actual container DNS name and internal WebUI port from your stack.

## RogueRoute GPX cards

When Docker discovery finds the standard RogueRoute container names, Rogue Dashboard applies these safe defaults:

| Container | Card behaviour |
| --- | --- |
| `rogueroute-gpx-web` | Opens `RGDASH_ROGUEROUTE_URL` and checks `http://rogueroute-gpx-web:9080/api/health`. |
| `rogueroute-gpx-osrm` | Status-only; checks `http://rogueroute-gpx-web:9080/api/health/osrm`. |
| `rogueroute-gpx-manager` | Status-only; checks `http://rogueroute-gpx-manager:9090/health`. |

All three use bundled local icons. Container-backed cards use Docker's native health state as the authoritative status and retain the private endpoint probe as a connection diagnostic. The dashboard installer and upgrader automatically join an existing `rogueroute-gpx` network when `RGDASH_EXTRA_NETWORK` is empty. Set it explicitly if automatic detection is not possible:

```dotenv
RGDASH_EXTRA_NETWORK=rogueroute-gpx
RGDASH_ROGUEROUTE_URL=https://gpx.example.com
```

Run `./upgrade.sh` after changing the value. Existing schema 6 cards are migrated to the current endpoints when the dashboard loads them.

## qBittorrent authentication order

For qBittorrent 5.2 or later, create an API key in the WebUI and set `RGDASH_QBITTORRENT_API_KEY`. Rogue Dashboard tries that bearer key first. If the key is absent or rejected and both fallback values are present, it performs a WebUI cookie login with the configured username and password.

Keeping all three values is valid and provides automatic fallback. **Customise → Connect** reports which method succeeded without returning the credentials.

## Legacy environment migration

`migrate-env.sh` converts recognised `HOMEPAGE_VAR_*` and `HOMEPAGE_*` keys into `RGDASH_*` keys. Existing `RGDASH_*` values win. The script creates `.env.pre-rgdash` once and never prints credential values.

```bash
./migrate-env.sh .env
```

Review the file after migration, restart the dashboard and keep both environment files private.
