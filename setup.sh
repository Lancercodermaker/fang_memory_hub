#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Personal Cloud Storage - One-Click Setup Script
# Run this inside the fang-dev container (/workspace/cloud/)
# ═══════════════════════════════════════════════════════════════

set -e

CLOUD_DIR="/workspace/cloud"
MINIO_VERSION="RELEASE.2025-01-20T14-49-07Z"

echo "═══════════════════════════════════════════════════"
echo "  Personal Cloud Storage - Setup"
echo "═══════════════════════════════════════════════════"

# ─── 1. Create directory structure ────────────────────────────
echo ""
echo "[1/5] Creating directory structure..."
mkdir -p "$CLOUD_DIR"/{minio/data,contexts,logs,indexes,rules,skills,setup-packages,api,bin}
echo "  ✓ Directories created"

# ─── 2. Download MinIO binary ─────────────────────────────────
echo ""
echo "[2/5] Downloading MinIO..."
MINIO_BIN="$CLOUD_DIR/bin/minio"
if [ -f "$MINIO_BIN" ]; then
    echo "  ✓ MinIO binary already exists, skipping download"
else
    curl -fSL "https://dl.min.io/server/minio/release/linux-amd64/minio" \
        -o "$MINIO_BIN"
    chmod +x "$MINIO_BIN"
    echo "  ✓ MinIO downloaded to $MINIO_BIN"
fi

# Verify MinIO
"$MINIO_BIN" --version || {
    echo "  ✗ MinIO binary verification failed!"
    exit 1
}

# ─── 3. Download MinIO Client (mc) ───────────────────────────
echo ""
echo "[3/5] Downloading MinIO Client (mc)..."
MC_BIN="$CLOUD_DIR/bin/mc"
if [ -f "$MC_BIN" ]; then
    echo "  ✓ mc binary already exists, skipping download"
else
    curl -fSL "https://dl.min.io/client/mc/release/linux-amd64/mc" \
        -o "$MC_BIN"
    chmod +x "$MC_BIN"
    echo "  ✓ mc downloaded to $MC_BIN"
fi

# ─── 4. Install Python dependencies ──────────────────────────
echo ""
echo "[4/5] Installing Python dependencies..."
cd "$CLOUD_DIR/api"

# Copy API source files if not already there
if [ ! -f "$CLOUD_DIR/api/main.py" ]; then
    echo "  ⚠ API source files not found in $CLOUD_DIR/api/"
    echo "  Please copy the Python files (main.py, auth.py, config.py, models.py, context.py)"
    echo "  to $CLOUD_DIR/api/ before running this script."
    echo ""
    echo "  From your local machine:"
    echo "  scp -P 6005 *.py requirements.txt fang@47.97.248.163:/workspace/cloud/api/"
    exit 1
fi

VENV_DIR="$CLOUD_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR" 2>/dev/null || {
        echo "  python3 venv module missing; installing python3-venv..."
        sudo apt update
        sudo apt install -y python3-venv
        python3 -m venv "$VENV_DIR"
    }
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$CLOUD_DIR/api/requirements.txt" --quiet
echo "  ✓ Python dependencies installed in $VENV_DIR"

# ─── 5. Generate config ──────────────────────────────────────
echo ""
echo "[5/5] Generating configuration..."

ENV_FILE="$CLOUD_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    echo "  ✓ .env already exists, skipping generation"
else
    # Generate random credentials
    MINIO_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
    API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

    cat > "$ENV_FILE" << EOF
# ═══ Personal Cloud Storage Configuration ═══
# Generated on $(date -u +"%Y-%m-%dT%H:%M:%SZ")

# MinIO Credentials
MINIO_ROOT_USER=fang-admin
MINIO_ROOT_PASSWORD=$MINIO_PASSWORD
MINIO_ENDPOINT=127.0.0.1:9000
MINIO_DEFAULT_BUCKET=personal-files

# API Settings
API_HOST=0.0.0.0
API_PORT=3000
API_KEYS=default:$API_KEY

# Storage
CLOUD_WORKSPACE=/workspace/cloud
MAX_UPLOAD_SIZE_MB=500
PUBLIC_BASE_URL=https://fang-cloud.mardio.top
EMBEDDING_PROVIDER=
EMBEDDING_API_KEY=
EOF

    echo "  ✓ .env file generated"
    echo ""
    echo "  ╔══════════════════════════════════════════════════╗"
    echo "  ║  🔑 SAVE THESE CREDENTIALS!                     ║"
    echo "  ╠══════════════════════════════════════════════════╣"
    echo "  ║  MinIO Password: $MINIO_PASSWORD"
    echo "  ║  API Key:        $API_KEY"
    echo "  ╚══════════════════════════════════════════════════╝"
    echo ""
    echo "  These are stored in $ENV_FILE"
fi

# ─── Done ─────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✓ Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Review $ENV_FILE"
echo "  2. Run: bash $CLOUD_DIR/start.sh"
echo "  3. Test: curl http://localhost:3000/health"
echo "═══════════════════════════════════════════════════"
