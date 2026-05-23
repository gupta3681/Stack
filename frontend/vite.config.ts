import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// When running inside Docker, the backend lives at "backend:8000" (Docker's
// internal DNS resolves the service name). When running natively via dev.sh,
// the backend is on the host at localhost:8000.
const proxyTarget = process.env.VITE_PROXY_TARGET ?? "http://localhost:8000";

// Docker on macOS uses a VM under the hood; native fs-event watching from a
// bind-mounted host directory is unreliable, so fall back to polling when
// CHOKIDAR_USEPOLLING is set by docker-compose.
const usePolling = process.env.CHOKIDAR_USEPOLLING === "true";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // bind 0.0.0.0 so the host can reach the dev server in Docker
    port: 5173,
    strictPort: true,
    watch: usePolling ? { usePolling: true, interval: 300 } : undefined,
    proxy: {
      "/api": {
        target: proxyTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
