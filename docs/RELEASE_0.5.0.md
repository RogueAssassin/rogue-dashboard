# Rogue Dashboard 0.5.0

Version 0.5.0 is the first fully public-facing release: a clean, from-scratch Docker experience backed by versioned GHCR images and generic documentation.

## Highlights

- A new colourful GitHub landing page with a three-command installation path.
- Personal deployment examples, domains, private addresses and environment defaults removed from the repository.
- Generic example fixtures now test imports without exposing a real installation.
- Electric Neon replaces the deployment-specific name of the default theme.
- Native select menus in the Customise panel now request the correct dark colour scheme and explicitly style options for readable contrast.
- qBittorrent 5.2+ API keys remain the primary authentication method; username/password login remains an automatic fallback.
- Existing `.env`, SQLite data and custom assets remain compatible.
- Upgrade handling no longer stops an unrelated container that owns the configured port; it exits with a clear message instead.
- Generic installation, configuration, network, proxy, upgrade, security and architecture guides are included.
- AMD64 and ARM64 images continue to be published from semantic version tags.

## Container tags

The 0.5.0 release commit publishes:

- `ghcr.io/rogueassassin/rogue-dashboard:0.5.0`
- `ghcr.io/rogueassassin/rogue-dashboard:0.5`
- `ghcr.io/rogueassassin/rogue-dashboard:latest`

## Upgrade

Keep `.env`, `data/` and `custom/`, update the repository deployment files, then run:

```bash
./upgrade.sh
```

The database schema remains compatible with 0.4.x. Read [Upgrading and recovery](UPGRADING.md) for backup and rollback details.
