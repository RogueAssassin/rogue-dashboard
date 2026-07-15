#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

version=$(sed -n 's/^VERSION = "\([0-9][0-9.]*\)"/\1/p' app/dashboard.py)
case "$version" in
  [0-9]*.[0-9]*.[0-9]*) ;;
  *) echo "app/dashboard.py must contain a semantic VERSION" >&2; exit 1 ;;
esac

require() {
  file=$1
  expected=$2
  if ! grep -Fq "$expected" "$file"; then
    echo "$file is not aligned with release $version (missing: $expected)" >&2
    exit 1
  fi
}

require app/integrations.py "Rogue-Dashboard/$version"
require app/static/app.js "|| \"$version\""
require app/static/index.html "favicon.svg?v=$version"
require Dockerfile "ARG RGDASH_VERSION=$version"
require docker-compose.build.yaml "RGDASH_VERSION: $version-dev"
require .env.example "rogueassassin/rogue-dashboard:$version"
require README.md "Version **$version**"
require CHANGELOG.md "## $version"
require "docs/RELEASE_$version.md" "# Rogue Dashboard $version"

echo "Release metadata is aligned for $version."
