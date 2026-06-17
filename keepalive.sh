#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Personal Cloud Storage - Keepalive Daemon
# Runs as a background cron job to auto-restart crashed services.
#
# Setup (run once):
#   chmod +x keepalive.sh
#   (crontab -l 2>/dev/null; echo "*/2 * * * * /workspace/cloud/keepalive.sh >> /workspace/cloud/logs/keepalive.log 2>&1") | crontab -
# ═══════════════════════════════════════════════════════════════

CLOUD_DIR="/workspace/cloud"
PID_DIR="$CLOUD_DIR/.pids"
LOG_DIR="$CLOUD_DIR/logs"
ENV_FILE="$CLOUD_DIR/.env"

# Load env
[ -f "$ENV_FILE" ] && { set -a; source "$ENV_FILE"; set +a; }

API_PORT="${API_PORT:-3000}"
PYTHON_BIN="$CLOUD_DIR/.venv/bin/python"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="python3"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

restart_if_dead() {
    local name="$1"
    local pid_file="$PID_DIR/$name.pid"
    local health_url="$2"
    local start_cmd="$3"

    # Check health endpoint first (most reliable)
    if curl -sf "$health_url" > /dev/null 2>&1; then
        return 0  # Healthy, nothing to do
    fi

    echo "[$TIMESTAMP] ⚠ $name health check failed, attempting restart..."

    # Kill stale PID if exists
    if [ -f "$pid_file" ]; then
        kill "$(cat "$pid_file")" 2>/dev/null || true
        rm -f "$pid_file"
    fi

    # Run restart command
    eval "$start_cmd"
    sleep 3

    # Verify restart
    if curl -sf "$health_url" > /dev/null 2>&1; then
        echo "[$TIMESTAMP] ✓ $name restarted successfully"
    else
        echo "[$TIMESTAMP] ✗ $name restart FAILED - manual intervention required"
    fi
}

# ─── MinIO ────────────────────────────────────────────────────
restart_if_dead "minio" \
    "http://127.0.0.1:9000/minio/health/live" \
    "MINIO_ROOT_USER='$MINIO_ROOT_USER' MINIO_ROOT_PASSWORD='$MINIO_ROOT_PASSWORD' \
     nohup $CLOUD_DIR/bin/minio server $CLOUD_DIR/minio/data \
       --address ':9000' --console-address ':9001' \
       >> $LOG_DIR/minio.log 2>&1 & echo \$! > $PID_DIR/minio.pid"

# ─── FastAPI ──────────────────────────────────────────────────
restart_if_dead "api" \
    "http://127.0.0.1:${API_PORT}/health" \
    "cd $CLOUD_DIR/api && \
     nohup $PYTHON_BIN -m uvicorn main:app --host 0.0.0.0 --port $API_PORT \
       >> $LOG_DIR/api.log 2>&1 & echo \$! > $PID_DIR/api.pid"
