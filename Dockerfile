FROM python:3.13-alpine

ARG RGDASH_VERSION=1.0.0

LABEL org.opencontainers.image.title="Rogue Dashboard" \
      org.opencontainers.image.description="Local-first Docker service dashboard" \
      org.opencontainers.image.source="https://github.com/RogueAssassin/rogue-dashboard" \
      org.opencontainers.image.url="https://github.com/RogueAssassin/rogue-dashboard" \
      org.opencontainers.image.version="${RGDASH_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    DATA_DIR=/data \
    STATIC_DIR=/app/static

WORKDIR /app
RUN addgroup -g 10001 dashboard \
    && adduser -D -u 10001 -G dashboard dashboard \
    && mkdir -p /data \
    && chown dashboard:dashboard /data

COPY --chown=dashboard:dashboard app/ /app/

USER dashboard
EXPOSE 8080
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "/app/dashboard.py", "healthcheck"]

ENTRYPOINT ["python", "/app/dashboard.py"]
