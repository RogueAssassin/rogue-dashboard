# Rogue Dashboard 1.0.0

Version 1.0.0 establishes the stable Docker-first release line and adds the administration controls needed for a long-running installation.

## Highlights

- **Customise → Admin** lists active administrator sessions, their last activity and expiry date.
- Any non-current session can be revoked without changing the administrator password or interrupting the current browser.
- A local action history records successful login/logout, dashboard saves, session revocation and successful or failed Docker lifecycle requests.
- Audit history is capped at 1,000 SQLite rows; the interface displays the newest 100.
- Existing session tables gain `created_at` and `last_seen_at` columns automatically and without deleting active sessions.
- The release includes documented support boundaries, migration guarantees, fresh-install, upgrade, staged-publish and rollback procedures.

## Stable compatibility promise

- `.env`, `data/` and `custom/` remain the persistent operator-owned paths.
- Dashboard JSON from 0.8 or later remains a supported restore format throughout the 1.x line.
- Minor 1.x upgrades will migrate stored data forward automatically. Any future breaking storage change requires explicit release notes and a backup-first path.

## Upgrade

Keep `.env`, `data/` and `custom/`, replace repository-controlled files and run `./upgrade.sh`. The first 1.0 start migrates the sessions table and creates the bounded action-audit table automatically.
