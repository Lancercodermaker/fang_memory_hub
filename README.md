# Personal Cloud Storage

A self-hosted file storage and AI agent context synchronization service. Built for the `fang-dev` container on the Guilin server.

## Architecture

```
Agent/Browser
    ↓ HTTPS
fang-cloud.mardio.top  (Nginx on public VPS)
    ↓ FRP tunnel
fang-dev container :3000  (FastAPI gateway)
    ↓ S3 API
MinIO :9000  (file storage on /workspace, 797GB)
```

## Quick Start

### 1. Copy files to the container

From your local machine (Windows PowerShell):
```powershell
# Copy all project files to the container
scp -P 6005 -r * fang@47.97.248.163:/workspace/cloud/api/
```

Or from WSL/Git Bash:
```bash
scp -P 6005 *.py requirements.txt *.sh fang@47.97.248.163:/workspace/cloud/
scp -P 6005 *.py requirements.txt fang@47.97.248.163:/workspace/cloud/api/
```

### 2. SSH into the container and run setup

```bash
ssh -p 6005 fang@47.97.248.163

cd /workspace/cloud
chmod +x setup.sh start.sh stop.sh status.sh keepalive.sh
bash setup.sh
```

**Save the API key printed by setup.sh!**

### 3. Start services

```bash
bash start.sh
```

### 4. Test locally (inside the container)

```bash
# Health check
curl http://localhost:3000/health

# List files (replace with your actual key from .env)
API_KEY=$(grep API_KEYS /workspace/cloud/.env | cut -d: -f3)
curl -H "X-API-Key: $API_KEY" http://localhost:3000/v1/files/list
```

### 5. Ask your friend to configure FRP + Nginx

Send them this configuration request:

**FRP** - add one new proxy rule in `frps.toml`:
```toml
# fang-dev Web API
[[proxies]]
name = "fang-web-api"
type = "tcp"
local_ip = "127.0.0.1"
local_port = 3000
remote_port = 8085
```

**Nginx** - add a new server block:
```nginx
server {
    listen 80;
    server_name fang-cloud.mardio.top;
    client_max_body_size 500M;

    location / {
        proxy_pass http://127.0.0.1:8085;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
```

Then request HTTPS via Let's Encrypt for `fang-cloud.mardio.top`.

### 6. Set up keepalive cron

```bash
(crontab -l 2>/dev/null; echo "*/2 * * * * /workspace/cloud/keepalive.sh >> /workspace/cloud/logs/keepalive.log 2>&1") | crontab -
```

---

## Using the Python Client (from your local machine or agent)

```bash
pip install requests
```

```python
from cloud_client import CloudClient

client = CloudClient(
    base_url="https://fang-cloud.mardio.top",
    api_key="your-api-key-from-env",
)

# Health check
print(client.health())

# Upload a file
client.upload_file("myfile.txt", remote_path="projects/my-project")

# Download a file
client.download_file("projects/my-project/myfile.txt", "local_copy.txt")

# Save agent context before switching tools
session_id = client.new_session_id()
client.save_context(
    session_id=session_id,
    project="my-project",
    agent_tool="antigravity",
    summary="Implemented the file upload API. Tests pass. Next: deploy FRP config.",
    pending_tasks=["configure FRP", "test public HTTPS endpoint"],
    relevant_files=["/workspace/cloud/api/main.py"],
)

# In another tool: resume from where you left off
ctx = client.get_latest_context("my-project")
print(ctx["summary"])
print(ctx["pending_tasks"])
```

Run the built-in demo test:
```bash
CLOUD_BASE_URL=https://fang-cloud.mardio.top \
FANG_CLOUD_API_KEY=your-api-key \
python3 cloud_client.py
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (no auth) |
| POST | `/v1/files/upload` | Upload a file |
| GET | `/v1/files/download/{path}` | Download a file |
| GET | `/v1/files/list` | List files |
| DELETE | `/v1/files/{path}` | Delete a file |
| POST | `/v1/context/save` | Save agent context |
| GET | `/v1/context/{session_id}` | Load context |
| GET | `/v1/context/latest/{project}` | Latest context for project |
| GET | `/v1/context/list` | List contexts |
| POST | `/v1/context/{session_id}/log` | Append raw log entry |
| GET | `/v1/context/stats` | Context storage stats |
| GET | `/v1/buckets` | List MinIO buckets |
| POST | `/v1/buckets/{name}` | Create bucket |

**Interactive API docs:** `https://fang-cloud.mardio.top/docs`

---

## File Structure

```
/workspace/cloud/
├── bin/
│   ├── minio          # MinIO binary
│   └── mc             # MinIO client (mc)
├── api/
│   ├── main.py        # FastAPI app
│   ├── auth.py        # API key auth + middleware
│   ├── config.py      # Configuration
│   ├── models.py      # Pydantic schemas
│   ├── context.py     # Context manager
│   └── requirements.txt
├── minio/data/        # File storage (uses /workspace 797GB)
├── contexts/          # Agent context JSON files
├── logs/              # Service logs
├── .pids/             # PID files for service management
├── .env               # Your credentials (keep secret!)
├── setup.sh           # One-time setup
├── start.sh           # Start all services
├── stop.sh            # Stop all services
├── status.sh          # Check service status
└── keepalive.sh       # Cron-based auto-restart
```

---

## Management Commands

```bash
# Check status
bash /workspace/cloud/status.sh

# View API logs (live)
tail -f /workspace/cloud/logs/api.log

# View MinIO logs
tail -f /workspace/cloud/logs/minio.log

# Restart everything
bash /workspace/cloud/stop.sh && bash /workspace/cloud/start.sh

# Check your API key
grep API_KEYS /workspace/cloud/.env
```

---

## Adding Multiple API Keys

Different keys for different tools — enables per-tool audit logging:

```bash
# Edit .env
# Format: name1:secret1,name2:secret2
API_KEYS=antigravity:key1abc,cursor:key2def,mobile:key3ghi

# Restart API to pick up new keys
bash /workspace/cloud/stop.sh && bash /workspace/cloud/start.sh
```

---

## Agent Bootstrap MVP

Agent Bootstrap lets new agent tools discover the correct project context, canonical rules, and remote-readable skills without scanning an entire workspace.

### Web Console

Start the API and open:

```text
http://localhost:3000/console/
```

Use the console to:

- Run a bootstrap test.
- Generate a setup prompt for a new Agent.
- Run smoke tests.
- Verify rules and skills endpoints.

### New Agent Onboarding

1. Open the Web console.
2. Enter API base URL and API key.
3. Choose an agent name, or keep `generic`.
4. Generate a setup prompt.
5. Paste the prompt into the new Agent.
6. The Agent should call `/v1/bootstrap`, read rules, read remote skills, and save context before ending work.

### Core Bootstrap Endpoints

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/v1/bootstrap` | Return project candidates, rules, contexts, skills, and next actions |
| GET | `/v1/rules/current` | Return canonical Markdown and JSON rules |
| GET | `/v1/rules/render` | Render Markdown rules for an agent/profile |
| GET | `/v1/skills/registry` | Return remote-readable skill registry |
| GET | `/v1/skills/{skill_id}/read` | Return `SKILL.md` content |
| GET | `/v1/index/projects` | List indexed project profiles |
| POST | `/v1/index/search` | Search project index by metadata |
| GET | `/v1/setup/prompt` | Generate non-secret setup prompt |
| GET | `/v1/setup/package` | Download non-secret setup package zip |
| GET | `/v1/tests/smoke` | Return smoke test report |

### Smoke Tests

Run from the Web console, or with curl:

```bash
curl -H "X-API-Key: $FANG_CLOUD_API_KEY" https://fang-cloud.mardio.top/v1/tests/smoke
```

The smoke report checks health, auth, rules, skills, and bootstrap contracts. It does not include complete API keys or secrets.

---

## Future Extensions

- **API Key Proxy**: Add `/v1/proxy/openai` endpoint to relay LLM API calls
- **Personal Website**: Add static file serving via Nginx
- **Backup to B2**: Add rclone sync job for Backblaze B2
- **MinIO Lifecycle**: Auto-archive files older than 30 days
