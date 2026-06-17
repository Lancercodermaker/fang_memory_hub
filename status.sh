#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Personal Cloud Storage - Service Status
# ═══════════════════════════════════════════════════════════════

CLOUD_DIR="/workspace/cloud"
PID_DIR="$CLOUD_DIR/.pids"
LOG_DIR="$CLOUD_DIR/logs"

echo "═══════════════════════════════════════════════════"
echo "  Personal Cloud Storage - Status"
echo "═══════════════════════════════════════════════════"

check_service() {
    local name="$1"
    local port="$2"
    local health_url="$3"
    local pid_file="$PID_DIR/$name.pid"
    
    echo ""
    echo "  ── $name ──"
    
    # Check PID
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "  PID:    $pid (running)"
        else
            echo "  PID:    $pid (dead ✗)"
        fi
    else
        echo "  PID:    not tracked"
    fi
    
    # Check port
    if ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq ":$port$"; then
        echo "  Port:   :$port (listening ✓)"
    elif [ -n "$health_url" ] && curl -sf "$health_url" > /dev/null 2>&1; then
        echo "  Port:   :$port (listening ✓)"
    else
        echo "  Port:   :$port (not listening ✗)"
    fi
    
    # Health check
    if [ -n "$health_url" ]; then
        local response
        response=$(curl -sf -w "%{http_code}" -o /dev/null "$health_url" 2>/dev/null)
        if [ "$response" = "200" ]; then
            echo "  Health: OK ✓"
        else
            echo "  Health: FAILED ✗ (HTTP $response)"
        fi
    fi
    
    # Log file
    local log_file="$LOG_DIR/$name.log"
    if [ -f "$log_file" ]; then
        local log_size=$(du -h "$log_file" | cut -f1)
        echo "  Log:    $log_file ($log_size)"
        echo "  Last:   $(tail -1 "$log_file" 2>/dev/null | head -c 100)"
    fi
}

check_service "minio" "9000" "http://127.0.0.1:9000/minio/health/live"
check_service "api" "3000" "http://127.0.0.1:3000/health"

# ─── Disk Usage ───────────────────────────────────────────────
echo ""
echo "  ── Storage ──"
echo "  Workspace:"
df -h /workspace 2>/dev/null | tail -1 | awk '{print "    Total: "$2"  Used: "$3"  Available: "$4"  ("$5")"}'

echo "  MinIO data:"
if [ -d "$CLOUD_DIR/minio/data" ]; then
    du -sh "$CLOUD_DIR/minio/data" 2>/dev/null | awk '{print "    "$1}'
else
    echo "    (not created)"
fi

echo "  Contexts:"
if [ -d "$CLOUD_DIR/contexts" ]; then
    du -sh "$CLOUD_DIR/contexts" 2>/dev/null | awk '{print "    "$1}'
else
    echo "    (not created)"
fi

# ─── Memory ───────────────────────────────────────────────────
echo ""
echo "  ── Memory ──"
free -h 2>/dev/null | head -2

echo ""
echo "═══════════════════════════════════════════════════"
