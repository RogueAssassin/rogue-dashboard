# Rogue Dashboard 0.4.3 — GHCR runtime distribution

## What changed

- The normal Compose deployment pulls `ghcr.io/rogueassassin/rogue-dashboard:latest` and contains no local `build` section.
- `RGDASH_IMAGE` can optionally pin an exact version or immutable digest.
- The dashboard and restricted Docker agent continue to use the same image with separate permissions.
- Installs and upgrades pull before recreating containers, preserve bind-mounted data and verify container health.
- Failed upgrades restore the previous local image and `.env` backup.
- The host port can be changed with `RGDASH_PORT`; the container and Nginx target remain port `8080`.
- Compose now enables an init process and drops all Linux capabilities from both services.
- The displayed version comes from the running backend image, avoiding stale hard-coded UI versions.
- qBittorrent collection performs one torrent-list request per refresh.

## Publish

Push the source to `RogueAssassin/rogue-dashboard`, then create and push the release tag:

```bash
git tag v0.4.3
git push origin v0.4.3
```

The included workflow publishes `0.4.3`, `0.4` and `latest` image tags for AMD64 and ARM64.

## Upgrade

Keep the existing `.env`, `data/` and `custom/` directories, then run:

```bash
chmod +x upgrade.sh migrate-env.sh
./upgrade.sh
```

Nginx Proxy Manager remains configured with scheme `http`, hostname `rogue-dashboard` and container port `8080`.
