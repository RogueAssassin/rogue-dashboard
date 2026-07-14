FROM python:3.13-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    DATA_DIR=/data \
    STATIC_DIR=/app/static

WORKDIR /app
COPY app/ /app/

RUN addgroup -g 10001 dashboard \
    && adduser -D -u 10001 -G dashboard dashboard \
    && mkdir -p /data \
    && chown -R dashboard:dashboard /app /data

USER dashboard
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "/app/dashboard.py", "healthcheck"]

ENTRYPOINT ["python", "/app/dashboard.py"]
