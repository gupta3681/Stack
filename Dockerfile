# Production image for Stack: React static bundle + nginx + FastAPI.

FROM node:23-alpine AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/tsconfig.json frontend/vite.config.ts frontend/index.html ./
COPY frontend/src ./src
RUN npm run build


FROM python:3.12-slim AS backend-build
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv==0.5.11

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv sync --frozen --no-install-project 2>/dev/null || uv sync --no-install-project
COPY backend/app ./app
RUN uv sync --no-dev


FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates nginx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=backend-build /app/.venv ./.venv
COPY --from=backend-build /app/app ./app
COPY --from=frontend-build /app/dist /usr/share/nginx/html

RUN cat > /etc/nginx/nginx.conf <<'EOF'
worker_processes auto;
pid /tmp/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    server_tokens off;

    access_log /dev/stdout;
    error_log /dev/stderr warn;

    sendfile on;
    keepalive_timeout 65;

    client_body_temp_path /tmp/nginx/client_body;
    proxy_temp_path /tmp/nginx/proxy;
    fastcgi_temp_path /tmp/nginx/fastcgi;
    uwsgi_temp_path /tmp/nginx/uwsgi;
    scgi_temp_path /tmp/nginx/scgi;

    limit_req_zone $binary_remote_addr zone=auth_zone:10m rate=10r/m;

    server {
        listen 8080;
        server_name _;

        root /usr/share/nginx/html;
        index index.html;

        add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "DENY" always;
        add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        location ~ ^/api/auth/(login|signup)$ {
            limit_req zone=auth_zone burst=10 nodelay;
            rewrite ^/api/(.*)$ /$1 break;
            proxy_pass http://127.0.0.1:8000;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Connection "";
        }

        location /api/ {
            rewrite ^/api/(.*)$ /$1 break;
            proxy_pass http://127.0.0.1:8000;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Connection "";
        }

        location /assets/ {
            expires 1y;
            add_header Cache-Control "public, immutable";
            try_files $uri =404;
        }

        location / {
            try_files $uri $uri/ /index.html;
        }
    }
}
EOF

RUN cat > /app/start.py <<'EOF'
from __future__ import annotations

import signal
import subprocess
import sys
import time

processes: list[subprocess.Popen[bytes]] = []
stopping = False


def stop_all(*_: object) -> None:
    global stopping
    stopping = True
    for process in processes:
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + 10
    for process in processes:
        remaining = max(0, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> int:
    signal.signal(signal.SIGTERM, stop_all)
    signal.signal(signal.SIGINT, stop_all)

    api = subprocess.Popen(
        [
            "/app/.venv/bin/uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ]
    )
    nginx = subprocess.Popen(["nginx", "-g", "daemon off;"])
    processes.extend([api, nginx])

    while not stopping:
        for process in processes:
            code = process.poll()
            if code is not None:
                stop_all()
                return code
        time.sleep(0.5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
EOF

RUN useradd --create-home --shell /usr/sbin/nologin stack \
    && mkdir -p /tmp/nginx/client_body /tmp/nginx/proxy /tmp/nginx/fastcgi \
        /tmp/nginx/uwsgi /tmp/nginx/scgi /run/nginx /var/cache/nginx /var/lib/nginx \
    && chown -R stack:stack /app /usr/share/nginx/html /tmp/nginx /run/nginx \
        /var/cache/nginx /var/lib/nginx

USER stack
EXPOSE 8080

CMD ["python", "/app/start.py"]
