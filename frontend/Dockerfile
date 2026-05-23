FROM node:23-alpine

WORKDIR /app

# Install deps from the lockfile (reproducible). Cached layer so code edits
# don't trigger re-install.
COPY package.json package-lock.json* ./
RUN npm ci

# Copy the rest of the source. In docker-compose we also bind-mount ./frontend
# over /app so hot reload picks up host edits — this COPY is only the base
# layer for the first run.
COPY . .

EXPOSE 5173

# `--host` makes Vite bind to 0.0.0.0 so the host machine (your browser) can
# reach the dev server through the published port.
CMD ["npm", "run", "dev", "--", "--host"]
