# Rogue Dashboard 0.4.2 — Proxy and connection repair

## Upgrade

Extract the release over the existing `rogue-dashboard` directory and run `./upgrade.sh`. The archive does not contain `.env`, `data/`, saved users, Nginx data or custom assets. The upgrade creates a rollback backup before replacing containers.

## Reverse proxy

The dashboard now joins `media-net` in its primary Compose file. Nginx Proxy Manager therefore reaches it through Docker DNS using:

- domain: `dash.roguegaming.com.au`
- scheme: `http`
- forward hostname: `rogue-dashboard`
- forward port: `8080`
- Websockets, Force SSL and HTTP/2: enabled

The public host must not forward to `localhost`, host port `7805`, HTTPS port `8080`, or `homepage:3000`. Cloudflare Tunnel should publish `http://nginx-proxy-manager:80` when Nginx Proxy Manager owns the route.

Forwarded HTTPS is detected and produces Secure session cookies. `RGDASH_ALLOWED_HOSTS` is enforced only when it contains at least one configured hostname; container and loopback health-check names remain allowed.

## qBittorrent

qBittorrent WebUI API authentication uses `RGDASH_QBITTORRENT_USERNAME` and `RGDASH_QBITTORRENT_PASSWORD`, then retains the returned session cookie. Origin and Referer exactly match the private qBittorrent URL.

Version 0.4.1 exposed a bearer API-key option that the WebUI API does not use. When the old `RGDASH_QBITTORRENT_API_KEY` contains a value and the password is absent, `migrate-env.sh` copies it to the password field and adds the default `admin` username if required. The original variable and `.env.pre-rgdash` backup remain available for rollback.

## Radarr

Radarr remains on `http://radarr:7878`. The Connection centre now distinguishes an incomplete key before sending a request and directs the administrator to copy the complete 32-character API key from Radarr Settings > General > Security.

## Verification

Run:

```bash
sudo MEDIA_SERVER_DIR=/opt/media-server media-dashboard-proxy-doctor.sh
sudo MEDIA_SERVER_DIR=/opt/media-server media-health.sh
```

Then open Admin > Customise > Connect. It reports proxy HTTPS state, private DNS reachability, loaded environment names and API authentication without returning secret values.
