# Rogue Dashboard 1.0.1

Version 1.0.1 fixes RogueRoute GPX health reporting and makes container-backed status cards more reliable.

## What changed

- Web and OSRM cards now use the RogueRoute Web container's stable health contract: `/api/health` and `/api/health/osrm`.
- Docker's native `healthy`, `starting` and `unhealthy` state is authoritative when a card is linked to a container.
- A missing private network no longer creates a false red dot for a container Docker has confirmed healthy. Connection diagnostics still report that the private endpoint is unreachable.
- `install.sh` and `upgrade.sh` detect an existing `rogueroute-gpx` network when `RGDASH_EXTRA_NETWORK` is empty and persist the correct setting.
- Stored dashboard schema 7 migrates existing RogueRoute cards without changing unrelated custom cards.
- Docker discovery and health tooltips now explain whether status came from Docker, the endpoint, or both.

## Upgrade

Update the Git checkout, then run the guarded upgrader:

```bash
cd /path/to/rogue-dashboard
git pull --ff-only
./upgrade.sh
```

If `RGDASH_EXTRA_NETWORK` already names another application network, keep it and follow the multiple-network guidance in `docs/INSTALLATION.md`. RogueRoute's native container status will still be shown, but its private HTTP probes require a shared network.

After both applications are updated, **RogueRoute GPX Web** and **RogueRoute OSRM** should settle on green dots. **Customise → Connect** shows the health source and any remaining network warning.
