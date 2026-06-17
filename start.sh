#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Personal Cloud Storage - Start All Services
# ═══════════════════════════════════════════════════════════════

set -e

CLOUD_DIR="/workspace/cloud"
ENV_FILE="$CLOUD_DIR/.env"
LOG_DIR="$CLOUD_DIR/logs"
PID_DIR="$CLOUD_DIR/.pids"
PYTHON_BIN="$CLOUD_DIR/.venv/bin/python"

mkdir -p "$LOG_DIR" "$PID_DIR"

# Load environment
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
else
    echo "✗ .env file not found. Run setup.sh first."
    exit 1
fi

echo "═══════════════════════════════════════════════════"
echo "  Starting Personal Cloud Storage Services"
echo "═══════════════════════════════════════════════════"

# ─── Start MinIO ──────────────────────────────────────────────
echo ""
echo "[1/2] Starting MinIO..."

# Check if already running
if [ -f "$PID_DIR/minio.pid" ] && kill -0 "$(cat "$PID_DIR/minio.pid")" 2>/dev/null; then
    echo "  ✓ MinIO already running (PID $(cat "$PID_DIR/minio.pid"))"
else
    MINIO_ROOT_USER="$MINIO_ROOT_USER" \
    MINIO_ROOT_PASSWORD="$MINIO_ROOT_PASSWORD" \
    nohup "$CLOUD_DIR/bin/minio" server "$CLOUD_DIR/minio/data" \
        --address ":9000" \
        --console-address ":9001" \
        > "$LOG_DIR/minio.log" 2>&1 &
    
    MINIO_PID=$!
    echo "$MINIO_PID" > "$PID_DIR/minio.pid"
    
    # Wait for MinIO to be ready
    echo "  Waiting for MinIO to start..."
    for i in $(seq 1 15); do
        if curl -sf http://127.0.0.1:9000/minio/health/live > /dev/null 2>&1; then
            echo "  ✓ MinIO started (PID $MINIO_PID)"
            break
        fi
        if [ $i -eq 15 ]; then
            echo "  ✗ MinIO failed to start. Check $LOG_DIR/minio.log"
            exit 1
        fi
        sleep 1
    done
fi

# ─── Start FastAPI ────────────────────────────────────────────
echo ""
echo "[2/2] Starting FastAPI Gateway..."

if [ -f "$PID_DIR/api.pid" ] && kill -0 "$(cat "$PID_DIR/api.pid")" 2>/dev/null; then
    echo "  ✓ FastAPI already running (PID $(cat "$PID_DIR/api.pid"))"
else
    cd "$CLOUD_DIR/api"
    if [ ! -x "$PYTHON_BIN" ]; then
        PYTHON_BIN="python3"
    fi
    
    nohup "$PYTHON_BIN" -m uvicorn main:app \
        --host "$API_HOST" \
        --port "$API_PORT" \
        --log-level info \
        > "$LOG_DIR/api.log" 2>&1 &
    
    API_PID=$!
    echo "$API_PID" > "$PID_DIR/api.pid"
    
    # Wait for API to be ready
    echo "  Waiting for API to start..."
    for i in $(seq 1 10); do
        if curl -sf http://127.0.0.1:${API_PORT}/health > /dev/null 2>&1; then
            echo "  ✓ FastAPI started (PID $API_PID)"
            break
        fi
        if [ $i -eq 10 ]; then
            echo "  ✗ FastAPI failed to start. Check $LOG_DIR/api.log"
            exit 1
        fi
        sleep 1
    done
fi

# ─── Status ───────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✓ All services started!"
echo ""
echo "  MinIO:    http://127.0.0.1:9000  (S3 API)"
echo "  MinIO UI: http://127.0.0.1:9001  (Web Console)"
echo "  API:      http://127.0.0.1:${API_PORT}  (Gateway)"
echo "  API Docs: http://127.0.0.1:${API_PORT}/docs"
echo ""
echo "  Logs:     $LOG_DIR/"
echo "  PIDs:     $PID_DIR/"
echo ""
echo "  Quick test:"
echo "    curl http://localhost:${API_PORT}/health"
echo "═══════════════════════════════════════════════════"
