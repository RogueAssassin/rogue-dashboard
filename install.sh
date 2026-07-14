#!/bin/sh
set -eu

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker was not found. Install Docker Desktop with WSL integration, then run this again."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 was not found. Update Docker Desktop, then run this again."
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

agent_token="$(sed -n 's/^DOCKER_AGENT_TOKEN=//p' .env | tail -n 1)"
if [ -z "$agent_token" ]; then
  agent_token="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"
  set_value DOCKER_AGENT_TOKEN "$agent_token"
fi

mkdir -p data
chmod 770 data
mkdir -p custom/icons custom/backgrounds
chmod 775 custom custom/icons custom/backgrounds

chmod +x migrate-env.sh
./migrate-env.sh .env

if ! docker network inspect media-net >/dev/null 2>&1; then
  echo "Creating media-net for dashboard, Nginx and service discovery."
  docker network create media-net >/dev/null
fi
docker compose -f docker-compose.yaml up -d --build

echo ""
echo "Rogue Dashboard is starting at http://localhost:7805"
echo "Nginx Proxy Manager target: http://rogue-dashboard:8080"
