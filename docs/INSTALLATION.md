# Installation and networking

This guide installs Rogue Dashboard from scratch by pulling its public GHCR image. The server does not need Python, Node.js or a source build toolchain.

## Requirements

- Docker Engine 24+ or a current Docker Desktop release
- Docker Compose v2
- A Linux-style shell for the helper scripts
- Permission to use the Docker daemon

## Recommended install

```bash
git clone https://github.com/RogueAssassin/rogue-dashboard.git
cd rogue-dashboard
chmod +x install.sh upgrade.sh migrate-env.sh
./install.sh
```

The installer is safe to rerun. It:

1. verifies Docker and Compose;
2. copies `.env.example` to `.env` only when `.env` is absent;
3. records the current user, group and Docker socket group IDs;
4. creates a random internal agent token;
5. prepares `data/`, `custom/icons/` and `custom/backgrounds/`;
6. migrates recognised legacy variable names without printing values;
7. creates the configured shared Docker network when needed;
8. pulls and starts the GHCR image;
9. waits for the dashboard health check.

Open `http://localhost:7805` after installation.

## Folder layout

| Path | Purpose | Back up? |
| --- | --- | --- |
| `.env` | Runtime settings and integration credentials | Yes |
| `data/` | SQLite database, users, sessions and dashboard layout | Yes |
| `custom/` | User icons and backgrounds | Yes |
| `backups/` | Timestamped upgrade backups | As needed |
| `docker-compose.yaml` | Runtime definition | Re-downloadable |

## Choose the host port

Set the left side of the port mapping through `.env`:

```dotenv
RGDASH_PORT=7805
```

Then recreate the dashboard:

```bash
docker compose up -d
```

Container port `8080` does not change. Reverse proxies on the shared Docker network should always target `rogue-dashboard:8080`.

## Shared network

Rogue Dashboard creates and joins `${MEDIA_NETWORK:-media-net}`. Attach monitored services and your reverse proxy to that same external network when you want container-name DNS:

```yaml
services:
  example-service:
    networks:
      - media-net

networks:
  media-net:
    external: true
```

You can select another network before installation:

```dotenv
MEDIA_NETWORK=proxy
```

The network must use the same name in each Compose project. A service cannot be reached by container name when it shares no network with the dashboard.

## Multiple Docker networks

Some applications use an isolated network that should not be replaced by `media-net`. Rogue Dashboard can join one additional existing network while its Docker agent stays private.

RogueRoute GPX creates the network `rogueroute-gpx`. When that network exists and `RGDASH_EXTRA_NETWORK` is empty, `install.sh` and `upgrade.sh` detect and configure it automatically. To set it yourself, use:

```dotenv
RGDASH_EXTRA_NETWORK=rogueroute-gpx
```

First, find the exact network attached to the target container:

```bash
docker inspect TARGET_CONTAINER \
  --format '{{range $name, $_ := .NetworkSettings.Networks}}{{println $name}}{{end}}'
```

Set that exact name in `.env`:

```dotenv
RGDASH_EXTRA_NETWORK=application-network
```

Apply the deployment:

```bash
./upgrade.sh
```

For a fresh install, set the value before running `./install.sh`. The network must already exist because its application stack owns it; Rogue Dashboard intentionally does not create or delete the extra network.

Verify both containers share it:

```bash
docker network inspect application-network \
  --format '{{range $id, $container := .Containers}}{{println $container.Name}}{{end}}'
```

An immediate, temporary test is also possible:

```bash
docker network connect application-network rogue-dashboard
```

Manual connections disappear if the dashboard container is recreated, so use `RGDASH_EXTRA_NETWORK` for the permanent configuration.

## WSL 2 notes

- Enable Docker Desktop integration for the Linux distribution that runs the scripts.
- Store the project inside the Linux filesystem for better bind-mount performance.
- Run `./install.sh` as your normal WSL user; use a Docker group or Docker Desktop integration rather than running the whole stack as root.

## Verify the deployment

```bash
docker compose ps
docker compose logs --tail=100 dashboard
curl --fail http://localhost:7805/api/ping
```

The dashboard and agent should both be healthy. The agent intentionally has no host port.

For RogueRoute, also verify its Web and OSRM containers and the shared network:

```bash
docker inspect rogueroute-gpx-web rogueroute-gpx-osrm \
  --format '{{.Name}} {{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}'
docker network inspect rogueroute-gpx \
  --format '{{range $id, $container := .Containers}}{{println $container.Name}}{{end}}'
```

`rogue-dashboard`, `rogueroute-gpx-web` and `rogueroute-gpx-osrm` should appear on the network. RogueRoute Manager may also appear because it belongs to that private application stack.
