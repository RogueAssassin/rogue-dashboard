#!/bin/sh
set -eu

env_file="${1:-.env}"
if [ ! -f "$env_file" ]; then
  echo "No $env_file file was found; nothing to migrate."
  exit 0
fi

legacy_count="$(awk -F= '/^HOMEPAGE(_VAR)?_[A-Za-z0-9_]*=/{count++} END{print count+0}' "$env_file")"

if [ "$legacy_count" -eq 0 ]; then
  echo "Environment names are already using the current RGDASH format."
  exit 0
fi

backup_file="${env_file}.pre-rgdash"
if [ ! -f "$backup_file" ]; then
  cp -p "$env_file" "$backup_file"
  chmod 600 "$backup_file" 2>/dev/null || true
fi

temporary="${env_file}.rgdash.$$"
trap 'rm -f "$temporary"' EXIT HUP INT TERM

awk '
function canonical(key) {
  if (key ~ /^HOMEPAGE_VAR_/) return "RGDASH_" substr(key, 14)
  if (key ~ /^HOMEPAGE_/) return "RGDASH_" substr(key, 10)
  return key
}
{
  line = $0
  separator = index(line, "=")
  if (separator > 1) {
    key = substr(line, 1, separator - 1)
    value = substr(line, separator + 1)
    converted = canonical(key)
    if (converted != key) {
      legacy_value[converted] = value
      legacy_order[++legacy_total] = converted
      next
    }
    if (key ~ /^RGDASH_/) existing[key] = 1
  }
  output[++output_total] = line
}
END {
  for (cursor = 1; cursor <= output_total; cursor++) print output[cursor]
  additions = legacy_total > 0
  if (additions) print ""
  if (additions) print "# Migrated automatically by Rogue Dashboard."
  for (cursor = 1; cursor <= legacy_total; cursor++) {
    key = legacy_order[cursor]
    if (!existing[key] && !written[key]) {
      print key "=" legacy_value[key]
      written[key] = 1
    }
  }
}
' "$env_file" > "$temporary"

chmod 600 "$temporary" 2>/dev/null || true
mv "$temporary" "$env_file"
trap - EXIT HUP INT TERM

echo "Migrated $legacy_count legacy Homepage name(s)."
echo "Backup retained at $backup_file"
