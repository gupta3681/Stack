"""Run nginx and FastAPI together in the single Fly.io image."""

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
