# Rogue Dashboard 0.4.1 — Port takeover and connections

## Upgrade order

1. Extract `rogue-dashboard-v0.4.1-port-takeover.zip` over the existing `rogue-dashboard` directory.
2. Run `chmod +x upgrade.sh && ./upgrade.sh` from that directory.
3. Confirm the saved dashboard opens at `http://localhost:7805`.
4. Extract `media-server-scripts-rgdash-v1.0.0.zip` separately.
5. Run its installer with `sudo MEDIA_SERVER_DIR=/opt/media-server ./install.sh`.

Do not delete `.env`, `data/` or `custom/`, and do not use `docker compose down -v`.

## Port and Homepage replacement

The dashboard upgrade detects whether Homepage owns port 7805, stops it immediately before the replacement starts, and disables its container restart policy after a successful dashboard health check. If the replacement fails, the previous dashboard is restored on port 8000 and Homepage is restarted.

The separate media-script installer removes `homepage` from the ordered startup arrays, adds `rogue-dashboard` last, applies `docker-compose.media-net.yaml`, and moves the old active Homepage directory under `/opt/media-server/retired/` only after port 7805 responds.

## qBittorrent

Rogue Dashboard now sends the matching Origin and Referer headers required by qBittorrent WebUI authentication.

- qBittorrent 5.2+: set `RGDASH_QBITTORRENT_API_KEY`.
- Earlier qBittorrent: set `RGDASH_QBITTORRENT_USERNAME` and `RGDASH_QBITTORRENT_PASSWORD`.
- Private URL: normally `http://qbittorrent:7800` for this media stack.

Use one authentication method. Restart the dashboard after changing `.env`.

## Radarr

- Set `RGDASH_RADARR_KEY` to the API key shown under Radarr settings.
- Private URL: normally `http://radarr:7878`.
- The collector now accepts a substantially larger movie response so large libraries do not fail at the old response cap.

## Connection test

Open **Customise → Connect → Test now**. The Connection Centre reports:

- whether the expected `RGDASH_*` names were loaded from `.env`;
- whether the private container hostname resolves over `media-net`;
- whether the configured port accepts the connection;
- whether the API accepted the credentials;
- response time and returned metric count.

No credential values are returned to the browser or written to dashboard exports.

## Interface migration

The schema migration removes the old Homepage card and consolidates the three website bookmarks into one horizontal menu in this order:

`GitHub → RogueGaming → Thoughtful Comms`

Each entry uses a bundled local SVG. The Customise panel now has working Appearance, Layout, Connect and Docker tabs, live title/subtitle preview, maximum-column selection, group reordering and appearance reset.
