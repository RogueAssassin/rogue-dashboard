# Support matrix

Rogue Dashboard is designed for Docker Compose installations that can run the published Linux container image.

| Component | Supported baseline |
| --- | --- |
| Docker Engine | 24 or newer |
| Docker Compose | Compose v2 (`docker compose`) |
| Architectures | Linux AMD64 and ARM64 |
| Hosts | Linux, WSL 2 with Docker Desktop integration, and compatible NAS/container hosts |
| Browsers | Current and previous major Chrome, Edge, Firefox and Safari |
| Reverse proxies | Any HTTP reverse proxy that preserves `Host` and `X-Forwarded-Proto` |
| Persistent storage | Local filesystem bind mounts with SQLite-safe locking semantics |

Production hosts do not require Node.js, pnpm, TypeScript or a host Python installation. Python is contained inside the published image.

Report reproducible problems with the Rogue Dashboard version, host platform, Docker/Compose versions, redacted Compose output and the newest relevant container logs. Never post `.env`, session cookies, API keys or the SQLite database publicly.

Community testing outside this matrix is welcome, but compatibility is not guaranteed until it is documented here.
