# Changelog

Rogue Dashboard follows semantic versioning for published container tags. Detailed upgrade notes live in `docs/`.

## 1.0.0

- Added active administrator-session review and protected revocation.
- Added a bounded, local administrative action history for login, logout, dashboard saves and Docker actions.
- Added automatic in-place migration for pre-1.0 session tables.
- Published a support matrix, migration policy and complete deployment guide.

See [the 1.0.0 release notes](docs/RELEASE_1.0.0.md).

## 0.8.0

- Added up to 20 named dashboard pages with page-aware groups and Docker discovery.
- Added page creation, renaming and guarded deletion to the live Customise panel.
- Added validated JSON restore during first setup and from the Connection centre.
- Migrated every existing single-page layout to a compatible Home page automatically.

See [the 0.8.0 release notes](docs/RELEASE_0.8.0.md).

## 0.7.0

- Added opt-in live CPU, memory and network counters to authenticated Docker discovery.
- Kept raw Docker statistics inside the restricted agent and returned only a bounded metric summary.
- Added opt-in successful-backup retention with failed-upgrade protection.
- Updated the repository's GitHub Actions to their validated current major versions.

See [the 0.7.0 release notes](docs/RELEASE_0.7.0.md).

## 0.6.0

- Added Docker network visibility and duplicate-safe container discovery.
- Added stable container links for discovered and migrated RogueRoute GPX cards.
- Improved Docker-agent failure feedback in the dashboard header.
- Hardened imports, static/custom asset serving, setup transactions and response headers.
- Added process limits, graceful shutdown and bounded container logs.
- Made GHCR publishing tag-only with release-alignment and Compose validation gates.
- Expanded operational documentation and the staged roadmap.

See [the 0.6.0 release notes](docs/RELEASE_0.6.0.md).

## 0.5.0

- Introduced the public pull-based GHCR installation flow and generic documentation.
- Added the red favicon, dark Customise controls and flexible second-network overlay.
- Added RogueRoute GPX presets and the qBittorrent 5.2+ API-key-first authentication path.

See [the 0.5.0 release notes](docs/RELEASE_0.5.0.md).
