# Roadmap

The 1.0 line establishes the stable Docker-first foundation. Future work remains gated by migration safety, a useful non-technical setup flow, WSL compatibility and a narrow Docker security boundary.

## Delivered through 1.0

- Browser setup, local authentication, SQLite persistence and backup-first upgrades.
- Multi-page service/bookmark layouts, search, live editing, themes and local artwork.
- Secret-safe Homepage import plus validated Rogue Dashboard JSON restore.
- Live media-service integrations and connection diagnostics.
- Restricted Docker discovery, network visibility, runtime metrics and confirmed lifecycle actions.
- Administrator session review, protected revocation and bounded action history.
- AMD64/ARM64 GHCR images with tag-gated, validated publishing.
- Documented support matrix, storage contract and forward migration policy.

## 1.1 direction: deeper operations

- Time-series container metrics with configurable local retention and storage budgets.
- Uptime Kuma status-page summaries and reusable integration presets.
- Per-widget refresh intervals and selectable metrics.
- Dedicated Docker socket, DNS and shared-network diagnostics.

## 1.2 direction: distributed installations

- Optional remote Docker agents with explicit host identity and per-host permissions.
- Page/group access policies and read-only operator roles.
- Full-instance encrypted backup export and validated restore manifests.
- Card template packs with a documented community contribution contract.

## Later exploration

- Optional identity-provider authentication behind supported reverse proxies.
- Personal favourites and per-user presentation settings.
- Safe embedded views only for applications that explicitly permit framing.
- Repository governance and an explicit source licence selected by the repository owner.

Requests are best proposed as focused GitHub issues with the user problem, expected behaviour, Docker topology and a redacted example configuration.
