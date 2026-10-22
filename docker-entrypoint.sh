#!/bin/sh
set -e

echo "[TechTrend Monitor] Applying database migrations..."
alembic upgrade head

echo "[TechTrend Monitor] Starting Uvicorn server on port 8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
