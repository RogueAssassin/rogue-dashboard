# Architecture

## Runtime layout

Rogue Dashboard is one Docker image used in two modes:

| Service | Network exposure | Responsibility |
| --- | --- | --- |
| Dashboard | Host port `7805`, internal port `8080` | UI, authentication, imports, persistence and service monitoring |
| Docker agent | Internal port `8081` only | Allow-listed Docker Engine metadata and container lifecycle actions |

The browser communicates only with the dashboard. The dashboard calls the agent over the isolated Compose network using a randomly generated bearer token. The agent is never published to the host.

## Application files

- `app/dashboard.py`: HTTP API, SQLite storage, authentication, Docker agent and health monitoring.
- `app/homepage_yaml.py`: constrained data-only reader for the Homepage YAML subset.
- `app/importer.py`: conversion into the versioned internal dashboard model.
- `app/integrations.py`: server-side service API clients, response timing and sanitized live metrics.
- `app/static`: browser-native interface with no compilation step.
- `app/static/icons`: bundled original offline service glyphs.
- `custom`: bind-mounted user icons and backgrounds, served read-only under `/custom/`.
- `docker-compose.yaml`: deploys on host port 7805 and joins the private agent network plus shared external `media-net`.
- `docker-compose.media-net.yaml`: compatibility file retained for older lifecycle scripts.

## Persistence

SQLite uses write-ahead logging inside the bind-mounted `data` directory. Administrator passwords are protected with `scrypt` and random salts. Session tokens are random, hashed in the database, HTTP-only and expire after 14 days.

Service widget credentials are resolved from `.env` only when a collector runs. Canonical variables use the `RGDASH_*` namespace, with a read-only legacy fallback for a safe transition. The public `/api/widgets` response contains display values, state, timing and configured/missing environment-variable names, but never their values. Results are cached for 25 seconds to avoid excessive polling.

`upgrade.sh` creates a private timestamped backup and preserves the previous container image as a local rollback tag before replacing running containers.

## Docker boundary

The agent implements only:

- `GET /health`
- authenticated `GET /containers`
- authenticated `POST /containers/{id}/start`
- authenticated `POST /containers/{id}/stop`
- authenticated `POST /containers/{id}/restart`

There is no general Docker proxy route.
