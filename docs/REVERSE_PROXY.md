# Reverse proxy guide

Run the reverse proxy on the same external Docker network as Rogue Dashboard. The upstream is always plain HTTP on container port `8080`:

```text
http://rogue-dashboard:8080
```

Do not point a proxy container at `localhost`; inside that container, `localhost` means the proxy itself. Do not use host port `7805` when Docker DNS is available.

## Nginx Proxy Manager

Create a Proxy Host using a domain you control, for example `dashboard.example.com`:

| Field | Value |
| --- | --- |
| Scheme | `http` |
| Forward Hostname / IP | `rogue-dashboard` |
| Forward Port | `8080` |
| Websockets Support | enabled |
| Block Common Exploits | enabled |

Request a valid certificate, then enable Force SSL and HTTP/2. Attach the Nginx Proxy Manager service to the same `${MEDIA_NETWORK:-media-net}` network.

## Nginx configuration

```nginx
server {
    listen 443 ssl http2;
    server_name dashboard.example.com;

    location / {
        proxy_pass http://rogue-dashboard:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Host validation and cookies

After the proxy works, restrict accepted hosts in `.env`:

```dotenv
RGDASH_ALLOWED_HOSTS=dashboard.example.com,localhost,127.0.0.1
RGDASH_TRUST_PROXY_HEADERS=true
SECURE_COOKIES=true
```

Recreate the dashboard after changing these values. Include every hostname used for direct health checks or LAN access, or leave `RGDASH_ALLOWED_HOSTS` empty.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `502 Bad Gateway` | Both containers share a network and the upstream is `rogue-dashboard:8080`. |
| Login loops over HTTPS | `X-Forwarded-Proto` is forwarded and Secure cookies match the access method. |
| Host not allowed | Add the exact hostname to `RGDASH_ALLOWED_HOSTS` or leave it empty. |
| Direct IP works, domain fails | Inspect DNS, certificate and proxy host configuration before changing the dashboard. |

