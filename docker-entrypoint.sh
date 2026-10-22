#!/bin/sh
set -e

# Wait for database readiness before running migrations
echo "[TechTrend Monitor] Checking database connection readiness..."
python - <<'EOF'
import os
import sys
import time
from urllib.parse import urlparse

db_url = os.getenv("DATABASE_URL", "")
if db_url.startswith("postgresql") or db_url.startswith("postgres"):
    import socket
    parsed = urlparse(db_url)
    host = parsed.hostname or "db"
    port = parsed.port or 5432
    max_retries = 30
    retry_interval = 1

    print(f"[TechTrend Monitor] Waiting for PostgreSQL database at {host}:{port} to be ready...")
    for attempt in range(1, max_retries + 1):
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"[TechTrend Monitor] Database port {port} reachable at {host}! Verifying engine connection...")
                break
        except (socket.error, OSError):
            if attempt == max_retries:
                print(f"[TechTrend Monitor] ERROR: Database at {host}:{port} not reachable after {max_retries} attempts.")
                sys.exit(1)
            time.sleep(retry_interval)

    from sqlalchemy import create_engine, text
    engine = create_engine(db_url)
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("[TechTrend Monitor] Database connection established successfully!")
            break
        except Exception as e:
            if attempt == max_retries:
                print(f"[TechTrend Monitor] ERROR: Failed to query database: {e}")
                sys.exit(1)
            time.sleep(retry_interval)
else:
    print(f"[TechTrend Monitor] Using SQLite / local database: {db_url}")
EOF

echo "[TechTrend Monitor] Applying database migrations..."
alembic upgrade head

echo "[TechTrend Monitor] Starting Uvicorn server on port 8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
