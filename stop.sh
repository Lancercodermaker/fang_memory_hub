#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Personal Cloud Storage - Stop All Services
# ═══════════════════════════════════════════════════════════════

CLOUD_DIR="/workspace/cloud"
PID_DIR="$CLOUD_DIR/.pids"

echo "═══════════════════════════════════════════════════"
echo "  Stopping Personal Cloud Storage Services"
echo "═══════════════════════════════════════════════════"

stop_service() {
    local name="$1"
    local pid_file="$PID_DIR/$name.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "  Stopping $name (PID $pid)..."
            kill "$pid"
            
            # Wait for graceful shutdown (max 10s)
            for i in $(seq 1 10); do
                if ! kill -0 "$pid" 2>/dev/null; then
                    echo "  ✓ $name stopped"
                    rm -f "$pid_file"
                    return 0
                fi
                sleep 1
            done
            
            # Force kill
            echo "  ⚠ Force killing $name..."
            kill -9 "$pid" 2>/dev/null
            rm -f "$pid_file"
            echo "  ✓ $name force stopped"
        else
            echo "  ✓ $name not running (stale PID file)"
            rm -f "$pid_file"
        fi
    else
        echo "  ✓ $name not running (no PID file)"
    fi
}

echo ""
stop_service "api"
stop_service "minio"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✓ All services stopped"
echo "═══════════════════════════════════════════════════"
