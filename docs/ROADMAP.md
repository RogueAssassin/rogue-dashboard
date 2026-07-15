# Roadmap

This roadmap describes direction, not promised dates. Every release must preserve Docker-native installation, safe migration, WSL compatibility, secret isolation and a usable browser setup flow.

## Delivered through 0.6

- Local administrator setup, SQLite persistence and secret-safe Homepage import.
- Responsive service and bookmark groups, search, live preview and drag-and-drop editing.
- Six themes, dual accents, background effects, density controls and local custom artwork.
- Live qBittorrent, Prowlarr, Radarr, Sonarr, Seerr, Bazarr, Tautulli and Pi-hole metrics.
- Connection diagnostics for Docker DNS, ports, API authentication and environment readiness.
- Restricted Docker discovery and confirmed start, stop and restart actions.
- Multi-network service access, Docker network visibility and duplicate-safe discovered cards.
- Pull-based AMD64/ARM64 GHCR deployment, backup-first upgrades and tag-gated publishing.

## 0.7 direction: operations visibility

- Opt-in container CPU, memory and network snapshots with strict local retention limits.
- Per-widget refresh intervals, selectable metrics and clearer last-success information.
- Uptime Kuma status-page summaries and reusable integration presets.
- A Docker diagnostics screen covering socket permissions, agent health and shared-network reachability.
- Configurable backup retention with a dry-run mode and free-space checks.

## 0.8 direction: pages and portability

- Multiple dashboard pages with page-level import and export.
- Safer full-instance backup and restore with manifest/version validation.
- Card templates and a documented community integration contract.
- Optional remote Docker agents with explicit host identity and per-host permissions.
- Keyboard-first editing, stronger focus handling and accessibility testing.

## 1.0 readiness

- Stable documented configuration and migration policy.
- Automated upgrade tests across supported release boundaries.
- Administrator session management and action audit history.
- Published support matrix for Docker Engine, Compose, architectures and browsers.
- Contributor governance, vulnerability reporting process and an explicit project licence chosen by the repository owner.

## Later exploration

- Role-aware page, group and Docker-action access.
- Personal favourites and per-user presentation settings.
- Optional identity-provider authentication behind supported reverse proxies.
- Safe embedded views only for applications that explicitly permit framing.

Requests are best proposed as focused GitHub issues with the user problem, expected behaviour, Docker topology and a redacted example configuration.
