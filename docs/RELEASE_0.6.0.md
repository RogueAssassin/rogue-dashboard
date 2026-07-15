# Rogue Dashboard 0.6.0

Version 0.6.0 focuses on dependable day-two operation. Existing `.env`, `data/` and `custom/` directories remain the upgrade boundary; no reset or reinstallation is required.

## Highlights

- Docker discovery now shows attached network names, sorts running containers first and recognises cards already linked to a container.
- Newly discovered cards retain a stable `containerName`, preventing accidental duplicates after a rename or rescan.
- Existing RogueRoute GPX Web, OSRM and Manager cards migrate to stable container links, bundled icons and their intended public/status-only behaviour.
- The header now clearly reports when the restricted Docker agent is unavailable instead of displaying only an empty counter.
- Container summaries continue to omit mounts, environment variables and unrelated labels.
- Legacy ZIP imports now enforce compressed, per-file, entry-count and total-expanded-size limits.
- Missing static assets return `404` instead of the application shell, and `/custom/` serves only common image formats up to 10 MB.
- First-time administrator creation is transaction-safe when two setup requests arrive together.
- Additional cross-origin and legacy-plugin response headers strengthen the default browser boundary; HTTPS requests receive HSTS.
- Dashboard and Docker-agent services now have process limits, graceful shutdown windows and bounded JSON log rotation.
- Release publishing is tag-only. CI checks tests, syntax, Compose overlays and version alignment before a multi-architecture image can be published.

## Container tags

Publishing Git tag `v0.6.0` produces:

- `ghcr.io/rogueassassin/rogue-dashboard:0.6.0`
- `ghcr.io/rogueassassin/rogue-dashboard:0.6`
- `ghcr.io/rogueassassin/rogue-dashboard:latest`

## Upgrade

Keep `.env`, `data/` and `custom/`, update the repository deployment files, then run:

```bash
./upgrade.sh
```

The dashboard model migrates from schema 4 to schema 5 automatically. The SQLite structure and authentication data remain compatible with 0.5.0. Read [Upgrading and recovery](UPGRADING.md) for backup and rollback details.
