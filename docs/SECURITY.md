# Security guidance

## Included safeguards

- The browser and main application never receive the Docker socket.
- The Docker agent has no published host port.
- A 256-bit token is generated during installation for internal agent requests.
- Agent routes are explicitly allow-listed.
- Docker actions require a logged-in administrator and a confirmation prompt.
- Passwords use `scrypt` with unique random salts.
- Session values are stored as hashes and sent through HTTP-only, SameSite Strict cookies.
- Administrators can review active sessions and revoke any session except the browser currently in use.
- Administrative actions are stored locally in a bounded audit table without credential values.
- Login attempts are rate-limited per client address.
- Imported literal credentials are discarded.
- Service API credentials are read server-side from `.env` and never returned by widget endpoints.
- Legacy environment names are migrated locally with values suppressed from console output; backups are permission-restricted.
- User-provided icons and backgrounds are mounted read-only and served only from the dedicated `/custom/` path.
- The Docker socket agent receives only its internal agent token, not media-service credentials.
- Saved dashboard data is length-limited and validated.
- Legacy ZIP imports cap compressed size, entry count, individual file size and total expansion size.
- Custom files are limited to common image formats and a 10 MB maximum.
- HTTP response security headers and a restrictive content policy are enabled.
- Containers use read-only root filesystems, temporary scratch mounts, process limits and `no-new-privileges`.
- Container logs rotate instead of growing without a bound.

## Important Docker warning

Anyone who can control a process with Docker socket access can potentially control the Docker host. The internal agent substantially reduces the exposed interface, but it must still be treated as privileged infrastructure.

Do not publish port 8081, attach the agent to public proxy networks or expose the dashboard directly through router port forwarding.

## Remote access

Prefer a private VPN or authenticated reverse proxy. Nginx Proxy Manager should forward `Host` and `X-Forwarded-Proto`; the dashboard then marks login cookies Secure automatically. `SECURE_COOKIES=true` can enforce the flag when a proxy does not send the protocol header.

```text
SECURE_COOKIES=true
```

Set `RGDASH_ALLOWED_HOSTS` to a comma-separated list when host-header enforcement is wanted. Leave it empty to retain direct LAN access by IP. Restart the stack after changing either setting.

## Backup protection

The SQLite database contains the password hash and active session hashes. Protect backups as you would protect other server configuration. The JSON layout export does not include password values or API secrets.
