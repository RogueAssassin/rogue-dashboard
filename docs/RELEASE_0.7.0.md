# Rogue Dashboard 0.7.0

Version 0.7.0 adds practical operations visibility without widening the Docker security boundary.

## Highlights

- **Customise → Docker** now shows CPU percentage, working memory and cumulative receive/transmit counters for running containers.
- Statistics are requested only for an authenticated Docker scan, limited to 100 running containers and collected with a bounded worker pool.
- The agent reduces Docker's raw statistics document to five display metrics; container environment, mounts and raw Engine data never reach the dashboard.
- `RGDASH_BACKUP_KEEP` optionally retains only the newest successful upgrade backups. The default `0` keeps everything, and failed upgrades never prune recovery data.
- GitHub Actions move to `actions/setup-python@v6`, `docker/setup-buildx-action@v4`, `docker/login-action@v4`, `docker/metadata-action@v6` and `docker/build-push-action@v7`.

## Upgrade

Keep `.env`, `data/` and `custom/`, replace the repository-controlled files, then run `./upgrade.sh`. No database migration or reset is required.
