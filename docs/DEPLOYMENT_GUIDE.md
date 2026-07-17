# Fresh install, upgrade and release guide

## Fresh installation

```bash
git clone https://github.com/RogueAssassin/rogue-dashboard.git
cd rogue-dashboard
chmod +x install.sh upgrade.sh migrate-env.sh
./install.sh
```

Open `http://localhost:7805`, create the local administrator and optionally restore a Rogue Dashboard JSON backup or import Homepage ZIP/YAML files.

The installer creates `.env` only when it is absent, generates the private agent token, detects host IDs, prepares `data/` and `custom/`, pulls GHCR images and waits for health.

## Normal upgrade

Back up or retain these operator-owned paths:

- `.env`
- `data/`
- `custom/`

Then run:

```bash
git pull --ff-only
./upgrade.sh
```

Do not replace `.env` with `.env.example`, delete `data/`, or run `docker compose down -v`. The upgrade script creates `backups/YYYYMMDD-HHMMSS/`, pulls before stopping, starts the replacement and rolls the image back if health fails.

## Publish staged releases with GitHub Desktop

Use this sequence when uploading the prepared 0.7.0, 0.8.0, 1.0.0 and 1.0.1 source folders.

1. In GitHub Desktop, clone `RogueAssassin/rogue-dashboard` and select `main`.
2. Copy the contents of the prepared `rogue-dashboard-v0.7.0` folder over the clone. Do not copy a real `.env`, `data`, `custom` artwork or `backups` directory.
3. Review the changed-file list, commit as `Release Rogue Dashboard 0.7.0`, and push.
4. Wait for both Validate jobs to pass in GitHub Actions.
5. On GitHub, create a release whose new tag is `v0.7.0` and targets the validated commit. Publishing that tag starts the GHCR workflow.
6. Verify the package contains `0.7.0`, `0.7` and `latest` tags.
7. Repeat with the prepared 0.8.0 folder and tag `v0.8.0` only after 0.7 succeeds.
8. Repeat with the prepared 1.0.0 folder and tag `v1.0.0` only after 0.8 succeeds.
9. Repeat with the prepared 1.0.1 folder and tag `v1.0.1` only after 1.0.0 succeeds.

Do not create all three tags first: the tag is the release gate and updates `latest`.

## Upgrade a live installation to a staged release

After its GHCR tag finishes publishing, pin the version in `.env` if desired:

```dotenv
RGDASH_IMAGE=ghcr.io/rogueassassin/rogue-dashboard:1.0.1
```

Then run `./upgrade.sh`. Verify `docker compose ps`, login, Docker discovery, service widgets, pages and **Customise → Admin**.

## Rollback

If `upgrade.sh` fails its health check, it automatically restores the previous local image and `.env`. For a manual rollback:

1. stop the stack;
2. restore the matching timestamped `data`, `.env` and `custom` backup;
3. pin the earlier image tag;
4. run `docker compose up -d --pull never`;
5. verify `/api/ping` and login before removing any backup.
