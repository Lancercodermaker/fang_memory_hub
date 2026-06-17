"""
Personal Cloud Storage - Python Client SDK

A lightweight client for AI agents to interact with the personal cloud API.
Supports file operations and agent context synchronization.

Usage:
    from cloud_client import CloudClient

    client = CloudClient(
        base_url="https://fang-cloud.mardio.top",
        api_key="your-key-here"
    )

    # Upload a file
    client.upload_file("notes.md")

    # Save agent context before switching tools
    client.save_context(
        session_id="my-session-uuid",
        project="my-project",
        agent_tool="antigravity",
        summary="Implemented MinIO file API. Next: deploy to container.",
        pending_tasks=["test upload endpoint", "configure FRP"],
    )

    # Resume context in another agent tool
    ctx = client.get_latest_context("my-project")
    print(ctx["summary"])
"""

import os
import uuid
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, BinaryIO

try:
    import requests
except ImportError:
    raise ImportError("Install requests: pip install requests")


class CloudClientError(Exception):
    """Raised when the cloud API returns an error."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class CloudClient:
    """
    Client for the Personal Cloud Storage API.
    
    Args:
        base_url: API base URL, e.g. "https://fang-cloud.mardio.top"
        api_key: Your API key (X-API-Key header)
        timeout: Request timeout in seconds
        verify_ssl: Whether to verify SSL certificates
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 60,
        verify_ssl: bool = True,
    ):
        self.base_url = (
            base_url
            or os.getenv("CLOUD_BASE_URL")
            or os.getenv("PUBLIC_BASE_URL")
            or ""
        ).rstrip("/")
        self.api_key = (
            api_key
            or os.getenv("FANG_CLOUD_API_KEY")
            or os.getenv("CLOUD_API_KEY")
            or ""
        )
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        if not self.base_url:
            raise ValueError(
                "base_url required. Pass it directly or set CLOUD_BASE_URL or PUBLIC_BASE_URL env var."
            )
        if not self.api_key:
            raise ValueError(
                "api_key required. Pass it directly or set FANG_CLOUD_API_KEY or CLOUD_API_KEY env var."
            )

        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Key": self.api_key,
            "Accept": "application/json",
        })

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _handle(self, response: requests.Response) -> dict:
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail") or response.json().get("error") or response.text
            except Exception:
                detail = response.text
            raise CloudClientError(response.status_code, str(detail))
        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        return {"content": response.content}

    # ─── Health ───────────────────────────────────────────────

    def health(self) -> dict:
        """Check API health. No auth required."""
        r = self.session.get(self._url("/health"), timeout=self.timeout, verify=self.verify_ssl)
        return self._handle(r)

    def ping(self) -> bool:
        """Quick reachability check. Returns True if API is up."""
        try:
            self.health()
            return True
        except Exception:
            return False

    # ─── Files ────────────────────────────────────────────────

    def upload_file(
        self,
        file_path: str | Path,
        remote_path: str = "",
        bucket: str = "",
    ) -> dict:
        """
        Upload a local file to cloud storage.

        Args:
            file_path: Local path to the file
            remote_path: Optional subdirectory in the bucket (e.g. "projects/myapp")
            bucket: Target bucket (defaults to personal-files)

        Returns:
            Upload response with file path and etag
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "rb") as f:
            r = self.session.post(
                self._url("/v1/files/upload"),
                files={"file": (file_path.name, f)},
                data={"path": remote_path, "bucket": bucket},
                timeout=max(self.timeout, 300),  # Extra time for large files
                verify=self.verify_ssl,
            )
        return self._handle(r)

    def upload_bytes(
        self,
        data: bytes,
        filename: str,
        remote_path: str = "",
        bucket: str = "",
    ) -> dict:
        """Upload raw bytes as a named file."""
        r = self.session.post(
            self._url("/v1/files/upload"),
            files={"file": (filename, data)},
            data={"path": remote_path, "bucket": bucket},
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        return self._handle(r)

    def download_file(self, remote_path: str, local_path: str | Path, bucket: str = "") -> Path:
        """
        Download a file from cloud storage.

        Args:
            remote_path: Path to the file in the bucket
            local_path: Where to save the downloaded file
            bucket: Source bucket (defaults to personal-files)

        Returns:
            Path to the downloaded file
        """
        params = {}
        if bucket:
            params["bucket"] = bucket

        r = self.session.get(
            self._url(f"/v1/files/download/{remote_path}"),
            params=params,
            stream=True,
            timeout=max(self.timeout, 300),
            verify=self.verify_ssl,
        )
        self._handle(r)  # Raises on error

        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)

        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        return local_path

    def download_bytes(self, remote_path: str, bucket: str = "") -> bytes:
        """Download a file and return its content as bytes."""
        params = {}
        if bucket:
            params["bucket"] = bucket

        r = self.session.get(
            self._url(f"/v1/files/download/{remote_path}"),
            params=params,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        self._handle(r)
        return r.content

    def list_files(self, prefix: str = "", bucket: str = "") -> list[dict]:
        """List files, optionally filtered by path prefix."""
        params = {}
        if prefix:
            params["prefix"] = prefix
        if bucket:
            params["bucket"] = bucket

        r = self.session.get(
            self._url("/v1/files/list"),
            params=params,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        return self._handle(r)["files"]

    def delete_file(self, remote_path: str, bucket: str = "") -> dict:
        """Delete a file from cloud storage."""
        params = {}
        if bucket:
            params["bucket"] = bucket

        r = self.session.delete(
            self._url(f"/v1/files/{remote_path}"),
            params=params,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        return self._handle(r)

    # ─── Agent Context ────────────────────────────────────────

    def save_context(
        self,
        session_id: str,
        project: str,
        agent_tool: str,
        summary: str,
        current_goal: str = "",
        completed_tasks: list[str] | None = None,
        pending_tasks: list[str] | None = None,
        key_decisions: list[dict] | None = None,
        relevant_files: list[str] | None = None,
        environment: dict | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """
        Save agent context for cross-tool synchronization.

        Call this at the end of a session or before switching tools.
        The 'summary' field is the most important — write it as if
        briefing a colleague who will continue your work.

        Args:
            session_id: Unique session ID (use str(uuid.uuid4()) for new sessions)
            project: Project name (e.g. "personal-cloud")
            agent_tool: Which tool you are ("antigravity", "cursor", "codex")
            summary: Natural language summary of current work state
            current_goal: What you're currently working on
            completed_tasks: List of completed task strings
            pending_tasks: List of pending task strings
            key_decisions: List of {"decision": str, "reason": str} dicts
            relevant_files: List of important file paths
            environment: Dict of environment info
            metadata: Any custom metadata dict

        Returns:
            Save confirmation with session_id
        """
        payload = {
            "session_id": session_id,
            "project": project,
            "agent_tool": agent_tool,
            "summary": summary,
            "current_goal": current_goal,
            "completed_tasks": completed_tasks or [],
            "pending_tasks": pending_tasks or [],
            "key_decisions": key_decisions or [],
            "relevant_files": relevant_files or [],
            "environment": environment or {},
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        r = self.session.post(
            self._url("/v1/context/save"),
            json=payload,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        return self._handle(r)

    def get_context(self, session_id: str) -> dict:
        """Load a specific agent context by session ID."""
        r = self.session.get(
            self._url(f"/v1/context/{session_id}"),
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        return self._handle(r)

    def get_latest_context(self, project: str, agent_tool: str = "") -> dict | None:
        """
        Get the most recently updated context for a project.

        Use this when resuming work:
            ctx = client.get_latest_context("my-project")
            if ctx:
                print("Resume from:", ctx["summary"])
                print("Pending tasks:", ctx["pending_tasks"])
        """
        params = {}
        if agent_tool:
            params["agent_tool"] = agent_tool

        try:
            r = self.session.get(
                self._url(f"/v1/context/latest/{project}"),
                params=params,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            return self._handle(r)
        except CloudClientError as e:
            if e.status_code == 404:
                return None
            raise

    def list_contexts(
        self,
        project: str = "",
        agent_tool: str = "",
        limit: int = 20,
    ) -> list[dict]:
        """List contexts with optional filtering."""
        params = {"limit": limit}
        if project:
            params["project"] = project
        if agent_tool:
            params["agent_tool"] = agent_tool

        r = self.session.get(
            self._url("/v1/context/list"),
            params=params,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        return self._handle(r)["contexts"]

    def append_log(self, session_id: str, role: str, content: str, **kwargs) -> dict:
        """
        Append a raw conversation log entry to a context's JSONL log.

        Args:
            session_id: The session to append to
            role: Message role ("user", "assistant", "system", "tool")
            content: Message content
            **kwargs: Any additional fields to include in the log entry
        """
        entry = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        }
        r = self.session.post(
            self._url(f"/v1/context/{session_id}/log"),
            json=entry,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        return self._handle(r)

    # ─── Agent Bootstrap ─────────────────────────────────────

    def bootstrap(self, payload: dict) -> dict:
        """Call the Agent bootstrap endpoint."""
        r = self.session.post(
            self._url("/v1/bootstrap"),
            json=payload,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        return self._handle(r)

    def list_projects(self) -> list[dict]:
        """List indexed projects."""
        r = self.session.get(
            self._url("/v1/index/projects"),
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        return self._handle(r)["projects"]

    def upsert_project(self, profile: dict) -> dict:
        """Create or update a project profile in the lightweight index."""
        r = self.session.post(
            self._url("/v1/index/projects"),
            json=profile,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        return self._handle(r)

    def search_index(
        self,
        query: str = "",
        project_id: str = "",
        git_remote: str = "",
        path_fingerprint: str = "",
        limit: int = 5,
    ) -> list[dict]:
        """Search project index using metadata fields."""
        r = self.session.post(
            self._url("/v1/index/search"),
            json={
                "query": query,
                "project_id": project_id,
                "git_remote": git_remote,
                "path_fingerprint": path_fingerprint,
                "limit": limit,
            },
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        return self._handle(r)["candidates"]

    def get_rules(self) -> dict:
        """Load canonical rules."""
        r = self.session.get(
            self._url("/v1/rules/current"),
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        return self._handle(r)

    def list_skills(self) -> dict:
        """Load skills registry."""
        r = self.session.get(
            self._url("/v1/skills/registry"),
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        return self._handle(r)

    def read_skill(self, skill_id: str) -> str:
        """Read a remote skill document."""
        r = self.session.get(
            self._url(f"/v1/skills/{skill_id}/read"),
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        return self._handle(r)["content"]

    # ─── Convenience Helpers ──────────────────────────────────

    def save_json(self, data: dict | list, remote_path: str, bucket: str = "") -> dict:
        """Serialize a Python dict/list to JSON and upload it."""
        content = json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        filename = remote_path.split("/")[-1]
        folder = "/".join(remote_path.split("/")[:-1])
        return self.upload_bytes(content, filename, remote_path=folder, bucket=bucket)

    def load_json(self, remote_path: str, bucket: str = "") -> dict | list:
        """Download a JSON file and parse it."""
        content = self.download_bytes(remote_path, bucket=bucket)
        return json.loads(content.decode("utf-8"))

    def new_session_id(self) -> str:
        """Generate a new unique session ID."""
        return str(uuid.uuid4())


# ─── Quick Demo ───────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    url = os.getenv("CLOUD_BASE_URL") or os.getenv("PUBLIC_BASE_URL")
    key = os.getenv("FANG_CLOUD_API_KEY") or os.getenv("CLOUD_API_KEY")

    if not url or not key:
        print("Usage: CLOUD_BASE_URL=https://fang-cloud.mardio.top FANG_CLOUD_API_KEY=xxx python3 cloud_client.py")
        sys.exit(1)

    client = CloudClient(base_url=url, api_key=key)

    print("── Health Check ──────────────────────────")
    h = client.health()
    print(f"  Status:    {h.get('status')}")
    print(f"  MinIO:     {h.get('minio_connected')}")
    print(f"  Storage:   {h.get('storage_used_gb')} / {h.get('storage_total_gb')} GB")
    print(f"  Uptime:    {h.get('uptime_seconds')}s")

    print("\n── Context Save/Load Test ───────────────")
    sid = client.new_session_id()
    client.save_context(
        session_id=sid,
        project="demo",
        agent_tool="demo-script",
        summary="Testing the cloud client SDK. Everything working correctly.",
        pending_tasks=["verify FRP tunnel", "configure Nginx"],
        relevant_files=["/workspace/cloud/api/main.py"],
    )
    print(f"  Saved context: {sid}")

    ctx = client.get_context(sid)
    print(f"  Loaded:    {ctx['summary']}")
    print(f"  Pending:   {ctx['pending_tasks']}")

    print("\n  ✓ Cloud client working correctly!")
