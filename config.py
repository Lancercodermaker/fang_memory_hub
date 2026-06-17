"""
Configuration module for Personal Cloud Storage.
All settings can be overridden via environment variables.
"""

import os
import secrets
from pathlib import Path

# ─── Base Paths ───────────────────────────────────────────────
WORKSPACE_ROOT = Path(os.getenv("CLOUD_WORKSPACE", "/workspace/cloud"))
MINIO_DATA_DIR = WORKSPACE_ROOT / "minio" / "data"
CONTEXT_DIR = WORKSPACE_ROOT / "contexts"
LOG_DIR = WORKSPACE_ROOT / "logs"
INDEX_DIR = WORKSPACE_ROOT / "indexes"
RULES_DIR = WORKSPACE_ROOT / "rules"
SKILLS_DIR = WORKSPACE_ROOT / "skills"
WEB_DIR = Path(__file__).resolve().parent / "web"
SETUP_PACKAGES_DIR = WORKSPACE_ROOT / "setup-packages"

# ─── MinIO Settings ──────────────────────────────────────────
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "fang-admin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
MINIO_DEFAULT_BUCKET = os.getenv("MINIO_DEFAULT_BUCKET", "personal-files")

# ─── API Settings ────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "3000"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://fang-cloud.mardio.top")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "")

# API Keys - comma-separated list for multi-key support
# Each key format: "name:secret" e.g. "antigravity:abc123,cursor:def456"
API_KEYS_RAW = os.getenv("API_KEYS", "")

# ─── Upload Limits ───────────────────────────────────────────
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# ─── Context Settings ────────────────────────────────────────
MAX_CONTEXT_SIZE_MB = int(os.getenv("MAX_CONTEXT_SIZE_MB", "50"))
CONTEXT_BACKUP_COUNT = int(os.getenv("CONTEXT_BACKUP_COUNT", "5"))


def parse_api_keys() -> dict[str, str]:
    """
    Parse API_KEYS env var into a dict of {name: secret}.
    Format: "name1:secret1,name2:secret2"
    If no keys configured, generate a default one and print it.
    """
    keys = {}
    if API_KEYS_RAW:
        for entry in API_KEYS_RAW.split(","):
            entry = entry.strip()
            if ":" in entry:
                name, secret = entry.split(":", 1)
                keys[name.strip()] = secret.strip()
    
    if not keys:
        # Generate a default key on first run
        default_key = secrets.token_urlsafe(32)
        keys["default"] = default_key
        print("=" * 60)
        print("WARNING: No API keys configured!")
        print(f"   Generated default key: {default_key}")
        print(f"   Set API_KEYS env var to persist:")
        print(f'   export API_KEYS="default:{default_key}"')
        print("=" * 60)
    
    return keys


def ensure_directories():
    """Create all required directories if they don't exist."""
    for d in [
        MINIO_DATA_DIR,
        CONTEXT_DIR,
        LOG_DIR,
        INDEX_DIR,
        RULES_DIR,
        SKILLS_DIR,
        SETUP_PACKAGES_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)


# Parse keys at module load time
API_KEYS = parse_api_keys()
