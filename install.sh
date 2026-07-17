#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker was not found. Install Docker Desktop with WSL integration, then run this again."
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 was not found. Update Docker Desktop, then run this again."
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "The Docker daemon is not available. Start Docker Desktop, then run this again."
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
fi

set_value() {
  key="$1"
  value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s/^${key}=.*/${key}=${value}/" .env
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}

set_value PUID "$(id -u)"
set_value PGID "$(id -g)"
if [ -S /var/run/docker.sock ]; then
  set_value DOCKER_GID "$(stat -c '%g' /var/run/docker.sock)"
fi

agent_token=$(sed -n 's/^DOCKER_AGENT_TOKEN=//p' .env | tail -n 1)
if [ -z "$agent_token" ]; then
  agent_token=$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')
  set_value DOCKER_AGENT_TOKEN "$agent_token"
fi
chmod 600 .env

mkdir -p data custom/icons custom/backgrounds
chmod 770 data
chmod 775 custom custom/icons custom/backgrounds
sh ./migrate-env.sh .env

media_network=$(sed -n 's/^MEDIA_NETWORK=//p' .env | tail -n 1)
media_network=${media_network:-media-net}
docker network inspect "$media_network" >/dev/null 2>&1 || docker network create "$media_network" >/dev/null

extra_network=$(sed -n 's/^RGDASH_EXTRA_NETWORK=//p' .env | tail -n 1)
if [ -z "$extra_network" ] && docker network inspect rogueroute-gpx >/dev/null 2>&1; then
  extra_network=rogueroute-gpx
  set_value RGDASH_EXTRA_NETWORK "$extra_network"
  echo "Detected RogueRoute GPX and enabled its private Docker network."
fi
if [ -n "$extra_network" ]; then
  if ! docker network inspect "$extra_network" >/dev/null 2>&1; then
    echo "The extra Docker network '$extra_network' does not exist."
    echo "Start its owning stack first, or correct RGDASH_EXTRA_NETWORK in .env."
    exit 1
  fi
  compose() { docker compose --env-file .env -f docker-compose.yaml -f docker-compose.extra-network.yaml "$@"; }
else
  compose() { docker compose --env-file .env -f docker-compose.yaml "$@"; }
fi
compose config -q

echo "Pulling Rogue Dashboard from GHCR..."
compose pull
compose up -d --remove-orphans --pull never

attempt=0
until [ "$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' rogue-dashboard 2>/dev/null || true)" = healthy ]; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "Rogue Dashboard did not become healthy within 60 seconds."
    compose logs --tail=100
    exit 1
  fi
  sleep 2
done

port=$(sed -n 's/^RGDASH_PORT=//p' .env | tail -n 1)
port=${port:-7805}
echo
echo "Rogue Dashboard is ready at http://localhost:$port"
echo "Nginx Proxy Manager target: http://rogue-dashboard:8080"
if [ -n "$extra_network" ]; then echo "Extra application network: $extra_network"; fi
