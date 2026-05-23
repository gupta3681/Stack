FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

# Install uv (Astral's package manager)
RUN pip install --no-cache-dir uv==0.5.11

WORKDIR /app

# Install dependencies first for better layer caching
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-install-project 2>/dev/null || uv sync --no-install-project

# Copy the application code
COPY app ./app

# Install the project itself
RUN uv sync --no-dev

RUN useradd --create-home --shell /usr/sbin/nologin stack \
    && chown -R stack:stack /app

EXPOSE 8000

USER stack

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
