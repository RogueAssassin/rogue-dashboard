# Upgrading and recovery

Rogue Dashboard separates replaceable deployment files from persistent data. An image upgrade should not remove your administrator account, dashboard layout, credentials or custom artwork.

## Before upgrading

Keep these paths:

- `.env`
- `data/`
- `custom/`

Do not replace `.env` with `.env.example`, delete `data/` or run `docker compose down -v`.

## Standard upgrade

```bash
git pull --ff-only
chmod +x upgrade.sh migrate-env.sh
./upgrade.sh
```

The script validates Compose, pulls the requested image while the old dashboard remains online, checks the configured port, stops briefly for a consistent backup, migrates legacy environment names, starts the replacement and waits for health.

Backups are written to `backups/YYYYMMDD-HHMMSS/`. If the new container does not become healthy, the script restores `.env` and retags the previously running local image before restarting the stack.

## Pin or roll back a release

Set a version in `.env`:

```dotenv
RGDASH_IMAGE=ghcr.io/rogueassassin/rogue-dashboard:0.5.0
```

Then run:

```bash
docker compose pull
docker compose up -d --pull never
```

To roll back manually, choose the earlier semantic version tag and repeat those commands. A newer database may not always be readable by a much older application, so retain the matching timestamped backup.

## Move to another host

1. Stop the stack with `docker compose down`.
2. Copy `.env`, `data/` and `custom/` to the same relative paths on the new host.
3. Copy or clone the current deployment files.
4. Run `./install.sh` to refresh host-specific IDs and start the image.
5. Verify login, custom assets and service-network connectivity.

Restrict copied files during transfer because `.env` contains API credentials and the SQLite database contains password and session hashes.

