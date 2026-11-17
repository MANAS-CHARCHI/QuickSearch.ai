#!/bin/sh
set -e

echo "[Vault City] Checking and applying database migrations..."

# Run Alembic migrations to bring database up to date
if command -v alembic >/dev/null 2>&1; then
    echo "[Vault City] Executing: alembic upgrade head"
    if alembic upgrade head; then
        echo "[Vault City] Database is up to date."
    else
        echo "[Vault City] Migration notice: tables may already exist. Ensuring revision tracking is aligned..."
        alembic stamp head || true
    fi
else
    echo "[Vault City] Alembic CLI not found; relying on FastAPI lifespan auto-init."
fi

echo "[Vault City] Starting service..."
exec "$@"
