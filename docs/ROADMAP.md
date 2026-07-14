# Roadmap

## 0.2 Docker-native foundation

- First-run visual setup.
- Homepage ZIP/YAML migration.
- Responsive services and bookmarks.
- Local authentication and persistence.
- Health checks and system overview.
- Restricted Docker discovery, start, stop and restart.
- Themes, drag-and-drop editing and backup export.

## 0.3 Service integrations (delivered)

- qBittorrent activity and transfer statistics.
- Radarr and Sonarr queue and health summaries.
- Prowlarr indexer health.
- Bazarr subtitle status.
- Tautulli streams and Plex activity.
- Pi-hole blocking and query statistics.
- Guided secret validation without storing raw credentials in dashboard exports.

## 0.4 Neon operations (delivered)

- Thoughtful Neon default and five additional theme presets.
- Adjustable background effect, dual accents, glow, card opacity and density.
- Homepage-style compact metric blocks and per-card response time.
- Expanded Prowlarr, Radarr, Sonarr and Pi-hole defaults plus Seerr support.
- Local icon registry and persistent custom asset mount.
- Combined container/API Connection Centre with manual retesting.
- Automatic, backup-first `HOMEPAGE_*` to `RGDASH_*` environment migration.

## 0.4.1 Port takeover and connections (delivered)

- Port 7805 takeover with Homepage shutdown and rollback handling.
- Persistent `media-net` startup through the media-server scripts.
- qBittorrent WebUI cookie authentication with environment-source diagnostics.
- Larger Radarr library responses and clearer DNS, port and credential errors.
- Functional Customise tabs, group reordering and maximum-column controls.
- Branded horizontal links menu and automatic removal of the old Homepage card.

## 0.4.2 Proxy and connection repair (delivered)

- Primary Compose attachment to `media-net` for Nginx and service DNS.
- Forwarded-HTTPS detection, Secure cookies and optional host allowlisting.
- Nginx Proxy Manager and Cloudflare route doctor for `dash.roguegaming.com.au`.
- qBittorrent WebUI username/password migration and Radarr key-shape diagnostics.

## 0.5 Operations and access

- Optional Uptime Kuma status-page summaries.
- Multiple Docker host agents and per-host capacity.
- Multiple dashboard pages and access roles.
- Container CPU, memory and network history with bounded retention.
- Action audit history and administrator session management.
- Personal favourites and safe embedded views for services that permit framing.
- Reverse-proxy and optional identity-provider authentication.
- Per-widget refresh, metric selection and update visibility.

WSL compatibility, data migration and rollback documentation remain release gates for every milestone.
