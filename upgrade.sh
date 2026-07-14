#!/bin/sh
set -eu

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is required to upgrade Rogue Dashboard."
  exit 1
fi

if [ ! -f docker-compose.yaml ] || [ ! -f .env ] || [ ! -d data ]; then
  echo "Run this from your existing rogue-dashboard folder. Its .env and data directory must still be present."
  exit 1
fi

docker network inspect media-net >/dev/null 2>&1 || docker network create media-net >/dev/null

compose() { docker compose -f docker-compose.yaml "$@"; }

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

upgrade_started=0
upgrade_finished=0
port_owner_id=""
port_owner_name=""
homepage_stopped=0
recover_on_failure() {
  status=$?
  if [ "$status" -ne 0 ] && [ "$upgrade_started" -eq 1 ] && [ "$upgrade_finished" -eq 0 ]; then
    echo "Upgrade did not complete; restarting the previous release..."
    if [ -f "$backup_dir/env.backup" ]; then
      cp "$backup_dir/env.backup" .env
      chmod 600 .env 2>/dev/null || true
    fi
    if [ -n "$old_image" ]; then
      docker image tag rogue-dashboard:rollback rogue-dashboard:local >/dev/null 2>&1 || true
    fi
    if [ "$homepage_stopped" -eq 1 ]; then
      sed -i 's/"7805:8080"/"8000:8080"/' docker-compose.yaml
    fi
    compose up -d --no-build >/dev/null 2>&1 || true
    if [ "$homepage_stopped" -eq 1 ] && [ -n "$port_owner_id" ]; then
      docker start "$port_owner_id" >/dev/null 2>&1 || true
    fi
  fi
  exit "$status"
}
trap recover_on_failure EXIT

echo "Building Rogue Dashboard 0.4.2 while the current version stays online..."
old_image="$(docker image inspect rogue-dashboard:local --format '{{.Id}}' 2>/dev/null || true)"
if [ -n "$old_image" ]; then
  docker image tag "$old_image" rogue-dashboard:rollback
fi
compose build

port_owner_line="$(docker ps --filter publish=7805 --format '{{.ID}} {{.Names}}' | head -n 1)"
if [ -n "$port_owner_line" ]; then
  port_owner_id="${port_owner_line%% *}"
  port_owner_name="${port_owner_line#* }"
  case "$port_owner_name" in
    rogue-dashboard|rogue-dashboard-*)
      port_owner_id=""
      port_owner_name=""
      ;;
    *homepage*|*Homepage*)
      echo "Homepage currently owns port 7805 and will be stopped for the Rogue Dashboard takeover."
      ;;
    *)
      echo "Port 7805 is already published by $port_owner_name. Stop or move that container, then rerun the upgrade."
      exit 1
      ;;
  esac
fi

timestamp="$(date +%Y%m%d-%H%M%S)"
backup_dir="backups/$timestamp"
mkdir -p "$backup_dir/data"
chmod 700 "$backup_dir" "$backup_dir/data"

echo "Stopping briefly for a consistent data backup..."
upgrade_started=1
compose stop dashboard docker-agent
cp -a data/. "$backup_dir/data/"
cp .env "$backup_dir/env.backup"
chmod 600 "$backup_dir/env.backup" 2>/dev/null || true
if [ -d custom ]; then
  cp -a custom "$backup_dir/custom"
fi
echo "Backup created at $backup_dir"

mkdir -p custom/icons custom/backgrounds
chmod 775 custom custom/icons custom/backgrounds
chmod +x migrate-env.sh
./migrate-env.sh .env

if env_has_value RGDASH_QBITTORRENT_USERNAME && env_has_value RGDASH_QBITTORRENT_PASSWORD; then
  echo "qBittorrent environment check: WebUI username and password are loaded."
else
  echo "WARNING: qBittorrent needs both RGDASH_QBITTORRENT_USERNAME and RGDASH_QBITTORRENT_PASSWORD in .env."
fi
if env_has_value RGDASH_RADARR_KEY; then
  echo "Radarr environment check: API key is loaded."
else
  echo "WARNING: RGDASH_RADARR_KEY is empty or missing in .env."
fi

if [ -n "$port_owner_id" ]; then
  docker stop "$port_owner_id" >/dev/null
  homepage_stopped=1
fi

echo "Starting the upgraded containers with the existing data..."
if ! compose up -d --no-build --remove-orphans; then
  echo "The new containers did not start."
  echo "Upgrade failed. Your backup remains at $backup_dir"
  exit 1
fi

attempt=0
until compose exec -T dashboard python /app/dashboard.py healthcheck >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "The containers started but the dashboard health check did not pass within 60 seconds."
    echo "Inspect with: docker compose -f docker-compose.yaml logs --tail=100"
    echo "Your data backup is at $backup_dir"
    exit 1
  fi
  sleep 2
done

upgrade_finished=1
trap - EXIT

if [ "$homepage_stopped" -eq 1 ]; then
  docker update --restart=no "$port_owner_id" >/dev/null 2>&1 || true
fi

echo ""
echo "Rogue Dashboard 0.4.2 is ready at http://localhost:7805"
echo "Nginx Proxy Manager target: http://rogue-dashboard:8080"
echo "Your administrator, saved layout and environment settings were preserved."
if [ "$homepage_stopped" -eq 1 ]; then
  echo "Homepage was stopped and its automatic restart policy was disabled."
fi
echo "Backup: $backup_dir"
