#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is required to upgrade Rogue Dashboard."
  exit 1
fi
if [ ! -f docker-compose.yaml ] || [ ! -f .env ] || [ ! -d data ]; then
  echo "Run this from the existing rogue-dashboard folder. Its .env and data directory must still be present."
  exit 1
fi

compose() { docker compose --env-file .env -f docker-compose.yaml "$@"; }
compose config -q

media_network=$(sed -n 's/^MEDIA_NETWORK=//p' .env | tail -n 1)
media_network=${media_network:-media-net}
docker network inspect "$media_network" >/dev/null 2>&1 || docker network create "$media_network" >/dev/null

env_has_value() {
  awk -v wanted="$1" '
    index($0, wanted "=") == 1 {
      value = substr($0, length(wanted) + 2)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      if (value != "" && value != "\"\"" && value != "\047\047") found = 1
    }
    END { exit(found ? 0 : 1) }
  ' .env
}

image_ref=$(compose config --images | sort -u | head -n 1)
old_image=$(docker inspect --format '{{.Image}}' rogue-dashboard 2>/dev/null || true)
upgrade_started=0
upgrade_finished=0
backup_dir=""

recover_on_failure() {
  status=$?
  if [ "$status" -ne 0 ] && [ "$upgrade_started" -eq 1 ] && [ "$upgrade_finished" -eq 0 ]; then
    echo "Upgrade did not complete; restoring the previous image and configuration..."
    if [ -n "$backup_dir" ] && [ -f "$backup_dir/env.backup" ]; then
      cp "$backup_dir/env.backup" .env
      chmod 600 .env 2>/dev/null || true
    fi
    if [ -n "$old_image" ] && [ -n "$image_ref" ]; then
      docker image tag "$old_image" "$image_ref" >/dev/null 2>&1 || true
      compose up -d --remove-orphans --pull never >/dev/null 2>&1 || true
    fi
  fi
  exit "$status"
}
trap recover_on_failure EXIT

echo "Pulling the requested Rogue Dashboard image while the current container remains online..."
compose pull

port=$(sed -n 's/^RGDASH_PORT=//p' .env | tail -n 1)
port=${port:-7805}
port_owner_line=$(docker ps --filter "publish=$port" --format '{{.ID}} {{.Names}}' | head -n 1)
if [ -n "$port_owner_line" ]; then
  port_owner_name=${port_owner_line#* }
  case "$port_owner_name" in
    rogue-dashboard|rogue-dashboard-*) : ;;
    *) echo "Port $port is already published by $port_owner_name. Stop or move it, then rerun the upgrade."; exit 1 ;;
  esac
fi

timestamp=$(date +%Y%m%d-%H%M%S)
backup_dir="backups/$timestamp"
mkdir -p "$backup_dir/data"
chmod 700 "$backup_dir" "$backup_dir/data"

echo "Stopping briefly for a consistent backup..."
upgrade_started=1
compose stop dashboard docker-agent
cp -a data/. "$backup_dir/data/"
cp .env "$backup_dir/env.backup"
chmod 600 "$backup_dir/env.backup" 2>/dev/null || true
if [ -d custom ]; then cp -a custom "$backup_dir/custom"; fi

mkdir -p custom/icons custom/backgrounds
chmod 775 custom custom/icons custom/backgrounds
sh ./migrate-env.sh .env

if env_has_value RGDASH_QBITTORRENT_API_KEY; then
  echo "qBittorrent environment check: the qBittorrent 5.2+ API key is loaded as the primary method."
elif env_has_value RGDASH_QBITTORRENT_USERNAME && env_has_value RGDASH_QBITTORRENT_PASSWORD; then
  echo "qBittorrent environment check: WebUI username/password fallback is loaded."
else
  echo "WARNING: qBittorrent needs RGDASH_QBITTORRENT_API_KEY or both username/password values in .env."
fi
if env_has_value RGDASH_RADARR_KEY; then
  echo "Radarr environment check: API key is loaded."
else
  echo "WARNING: RGDASH_RADARR_KEY is empty or missing in .env."
fi

compose up -d --remove-orphans --pull never
attempt=0
until [ "$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' rogue-dashboard 2>/dev/null || true)" = healthy ]; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "The new container did not become healthy within 60 seconds."
    compose logs --tail=100
    exit 1
  fi
  sleep 2
done

upgrade_finished=1
trap - EXIT

echo
running_version=$(docker exec rogue-dashboard python -c 'import json,urllib.request; print(json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/ping"))["version"])' 2>/dev/null || true)
echo "Rogue Dashboard ${running_version:-image} is ready at http://localhost:$port"
echo "Nginx Proxy Manager target: http://rogue-dashboard:8080"
echo "Backup: $backup_dir"
