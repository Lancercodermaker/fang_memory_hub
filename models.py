"""
Pydantic models for API request/response schemas.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


# ─── File Models ──────────────────────────────────────────────

class FileInfo(BaseModel):
    """Metadata about a stored file."""
    name: str
    path: str
    size: int = Field(description="File size in bytes")
    content_type: str = ""
    last_modified: Optional[datetime] = None
    etag: str = ""
    bucket: str = ""


class FileListResponse(BaseModel):
    """Response for file listing."""
    files: list[FileInfo]
    total: int
    prefix: str = ""
    bucket: str = ""


class FileUploadResponse(BaseModel):
    """Response after successful upload."""
    name: str
    path: str
    size: int
    bucket: str
    etag: str
    message: str = "File uploaded successfully"


class FileDeleteResponse(BaseModel):
    """Response after successful deletion."""
    name: str
    path: str
    message: str = "File deleted successfully"


# ─── Agent Context Models ────────────────────────────────────

class KeyDecision(BaseModel):
    """A key decision made during the agent session."""
    decision: str
    reason: str
    timestamp: Optional[datetime] = None


class AgentContext(BaseModel):
    """
    Structured agent context for cross-tool synchronization.
    This is the 'relay baton' when switching between Cursor/Codex/Antigravity.
    """
    session_id: str = Field(description="Unique session identifier (UUID)")
    project: str = Field(description="Project name or path")
    agent_tool: str = Field(
        description="Which agent tool created this context",
        examples=["antigravity", "cursor", "codex", "claude-code"]
    )
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Work state
    summary: str = Field(
        description="Natural language summary of current work state. "
                    "This is the most important field for resuming work."
    )
    current_goal: str = Field(default="", description="What the agent is currently working on")
    completed_tasks: list[str] = Field(default_factory=list)
    pending_tasks: list[str] = Field(default_factory=list)
    key_decisions: list[KeyDecision] = Field(default_factory=list)
    
    # File references
    relevant_files: list[str] = Field(
        default_factory=list,
        description="List of file paths relevant to current work"
    )
    
    # Environment info
    environment: dict = Field(
        default_factory=dict,
        description="Environment details (os, workspace path, etc.)"
    )
    
    # Raw context reference (stored separately as .jsonl for space efficiency)
    raw_context_ref: str = Field(
        default="",
        description="Path to raw conversation log file"
    )
    
    # Custom metadata
    metadata: dict = Field(
        default_factory=dict,
        description="Any additional custom metadata"
    )


class ContextListResponse(BaseModel):
    """Response for context listing."""
    contexts: list[AgentContext]
    total: int


class ContextSaveResponse(BaseModel):
    """Response after saving context."""
    session_id: str
    project: str
    message: str = "Context saved successfully"


# ─── Health / Status Models ──────────────────────────────────

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "1.0.0"
    minio_connected: bool = False
    storage_used_gb: float = 0.0
    storage_total_gb: float = 0.0
    uptime_seconds: float = 0.0


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: str = ""
    hint: str = ""


# ─── Agent Bootstrap Models ──────────────────────────────────

class AgentCapabilities(BaseModel):
    can_read_markdown: bool = True
    can_parse_json: bool = True
    can_call_http: bool = True
    can_run_shell: bool = False
    can_install_skills: bool = False
    supports_mcp: bool = False


class AgentDescriptor(BaseModel):
    name: str = Field(default="generic")
    version: str = Field(default="unknown")
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)


class BootstrapWorkspace(BaseModel):
    path: str = ""
    project_id: str = ""
    git_remote: str = ""
    git_branch: str = ""
    path_fingerprint: str = ""
    query: str = ""


class BootstrapLocalState(BaseModel):
    installed_skills: list[str] = Field(default_factory=list)
    known_rule_version: str = ""
    known_context_session_id: str = ""


class BootstrapPreferences(BaseModel):
    max_contexts: int = 5
    include_raw_logs: bool = False
    response_format: str = "markdown+json"


class BootstrapRequest(BaseModel):
    agent: AgentDescriptor
    workspace: BootstrapWorkspace
    local_state: BootstrapLocalState = Field(default_factory=BootstrapLocalState)
    preferences: BootstrapPreferences = Field(default_factory=BootstrapPreferences)


class CandidateProject(BaseModel):
    project_id: str
    score: float
    match_reasons: list[str] = Field(default_factory=list)


class BootstrapRulesInfo(BaseModel):
    canonical_version: str
    markdown_ref: str
    machine_ref: str


class BootstrapContextSummary(BaseModel):
    session_id: str
    summary: str
    current_goal: str = ""
    pending_tasks: list[str] = Field(default_factory=list)
    relevant_files: list[str] = Field(default_factory=list)
    updated_at: str = ""


class BootstrapSkillCandidate(BaseModel):
    skill_id: str
    reason: str
    read_url: str = ""
    install_plan_url: str = ""


class BootstrapSkillsInfo(BaseModel):
    runtime_read_candidates: list[BootstrapSkillCandidate] = Field(default_factory=list)
    install_candidates: list[BootstrapSkillCandidate] = Field(default_factory=list)
    already_available: list[str] = Field(default_factory=list)
    registry_ref: str = "/v1/skills/registry"


class BootstrapJsonPayload(BaseModel):
    rules: BootstrapRulesInfo
    contexts: list[BootstrapContextSummary] = Field(default_factory=list)
    skills: BootstrapSkillsInfo = Field(default_factory=BootstrapSkillsInfo)
    next_actions: list[str] = Field(default_factory=list)


class BootstrapResponse(BaseModel):
    bootstrap_id: str
    confidence: float
    selected_project_id: str = ""
    candidate_projects: list[CandidateProject] = Field(default_factory=list)
    markdown: str
    json: BootstrapJsonPayload


class ProjectProfile(BaseModel):
    project_id: str
    display_name: str = ""
    aliases: list[str] = Field(default_factory=list)
    git_remotes: list[str] = Field(default_factory=list)
    path_fingerprints: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    description: str = ""
    rules_profile: str = "default-agent-project"
    skill_sets: list[str] = Field(default_factory=list)
    last_active_at: str = ""


class IndexSearchRequest(BaseModel):
    project_id: str = ""
    git_remote: str = ""
    path_fingerprint: str = ""
    query: str = ""
    limit: int = 5


class IndexSearchResponse(BaseModel):
    candidates: list[CandidateProject]
