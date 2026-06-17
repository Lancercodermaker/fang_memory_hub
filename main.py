"""
Personal Cloud Storage API Gateway.

A self-hosted file storage and agent context synchronization service.
Designed to run inside the fang-dev Docker container on the Guilin server.

Architecture:
    Agent/Browser → fang-cloud.mardio.top → Nginx → FRP → This API → MinIO + Filesystem

Usage:
    uvicorn main:app --host 0.0.0.0 --port 3000
"""

import io
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query, Form
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from minio import Minio
from minio.error import S3Error

import config
from auth import verify_api_key, RateLimitMiddleware, RequestLoggingMiddleware
from bootstrap import BootstrapService
from models import (
    FileInfo, FileListResponse, FileUploadResponse, FileDeleteResponse,
    AgentContext, ContextListResponse, ContextSaveResponse,
    HealthResponse, ErrorResponse, BootstrapRequest, BootstrapResponse,
    ProjectProfile, IndexSearchRequest, IndexSearchResponse,
)
from context import ContextManager
from index_store import IndexStore
from rules_store import RulesStore
from setup_package import SetupPackageGenerator
from skills_store import SkillsStore
from smoke_tests import SmokeTestRunner

# ─── Globals ──────────────────────────────────────────────────
START_TIME = time.time()
minio_client: Optional[Minio] = None
context_manager: Optional[ContextManager] = None
index_store: Optional[IndexStore] = None
rules_store: Optional[RulesStore] = None
skills_store: Optional[SkillsStore] = None
bootstrap_service: Optional[BootstrapService] = None
setup_generator: Optional[SetupPackageGenerator] = None


def init_minio() -> Minio:
    """Initialize MinIO client and ensure default bucket exists."""
    client = Minio(
        config.MINIO_ENDPOINT,
        access_key=config.MINIO_ROOT_USER,
        secret_key=config.MINIO_ROOT_PASSWORD,
        secure=config.MINIO_SECURE,
    )
    
    # Ensure default bucket exists
    bucket = config.MINIO_DEFAULT_BUCKET
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        print(f"[MinIO] Created bucket: {bucket}")
    
    return client


def init_agent_cloud_services() -> None:
    """Initialize Agent Bootstrap stores and services."""
    global index_store, rules_store, skills_store, bootstrap_service, setup_generator

    if index_store and rules_store and skills_store and bootstrap_service and setup_generator:
        return

    index_store = IndexStore(config.INDEX_DIR)
    rules_store = RulesStore(config.RULES_DIR)
    skills_store = SkillsStore(config.SKILLS_DIR)
    bootstrap_service = BootstrapService(index_store, rules_store, skills_store)
    setup_generator = SetupPackageGenerator(rules_store, skills_store)


def require_agent_cloud_services() -> tuple[
    IndexStore,
    RulesStore,
    SkillsStore,
    BootstrapService,
    SetupPackageGenerator,
]:
    """Return initialized Agent Bootstrap services for request handlers."""
    init_agent_cloud_services()
    assert index_store is not None
    assert rules_store is not None
    assert skills_store is not None
    assert bootstrap_service is not None
    assert setup_generator is not None
    return index_store, rules_store, skills_store, bootstrap_service, setup_generator


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup and shutdown."""
    global minio_client, context_manager
    
    # Startup
    config.ensure_directories()
    init_agent_cloud_services()
    print("[API] Starting Personal Cloud Storage...")
    print(f"[API] Workspace: {config.WORKSPACE_ROOT}")
    print(f"[API] MinIO endpoint: {config.MINIO_ENDPOINT}")
    print(f"[API] Loaded {len(config.API_KEYS)} API key(s)")
    
    try:
        minio_client = init_minio()
        print("[MinIO] Connected successfully")
    except Exception as e:
        print(f"[MinIO] Connection failed: {e}")
        print("[MinIO] File API will be unavailable. Context API still works.")
    
    context_manager = ContextManager(index_store=index_store)
    print("[Context] Manager initialized")
    print("[Bootstrap] Stores initialized")
    print(f"[API] Listening on {config.API_HOST}:{config.API_PORT}")
    
    yield
    
    # Shutdown
    print("[API] Shutting down...")


# ─── FastAPI App ──────────────────────────────────────────────
app = FastAPI(
    title="Personal Cloud Storage",
    description=(
        "Self-hosted file storage and agent context synchronization API. "
        "Designed for AI agent workflows across Cursor, Codex, and Antigravity."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware (order matters: last added = first executed)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=200, window_seconds=60)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if config.WEB_DIR.exists():
    app.mount("/console", StaticFiles(directory=str(config.WEB_DIR), html=True), name="console")


# ─── Health ───────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {"service": "Personal Cloud Storage", "status": "running"}


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint (no auth required)."""
    minio_ok = False
    storage_used = 0.0
    
    if minio_client:
        try:
            minio_client.list_buckets()
            minio_ok = True
        except Exception:
            pass
    
    # Get workspace usage
    try:
        import shutil
        usage = shutil.disk_usage(str(config.WORKSPACE_ROOT))
        storage_used = round(usage.used / (1024**3), 2)
        storage_total = round(usage.total / (1024**3), 2)
    except Exception:
        storage_total = 0.0
    
    return HealthResponse(
        status="ok",
        minio_connected=minio_ok,
        storage_used_gb=storage_used,
        storage_total_gb=storage_total,
        uptime_seconds=round(time.time() - START_TIME, 1),
    )


# ─── File API ────────────────────────────────────────────────

@app.post(
    "/v1/files/upload",
    response_model=FileUploadResponse,
    tags=["Files"],
)
async def upload_file(
    file: UploadFile = File(...),
    path: str = Form(default="", description="Optional subdirectory path, e.g. 'projects/myapp'"),
    bucket: str = Form(default=""),
    key_name: str = Depends(verify_api_key),
):
    """
    Upload a file to MinIO storage.
    
    - **file**: The file to upload (multipart form data)
    - **path**: Optional subdirectory within the bucket
    - **bucket**: Target bucket (defaults to personal-files)
    """
    if not minio_client:
        raise HTTPException(status_code=503, detail="MinIO not available")
    
    bucket = bucket or config.MINIO_DEFAULT_BUCKET
    
    # Build object name
    object_name = f"{path}/{file.filename}" if path else file.filename
    object_name = object_name.lstrip("/")
    
    # Check file size
    content = await file.read()
    if len(content) > config.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {config.MAX_UPLOAD_SIZE_MB}MB"
        )
    
    try:
        result = minio_client.put_object(
            bucket,
            object_name,
            io.BytesIO(content),
            length=len(content),
            content_type=file.content_type or "application/octet-stream",
        )
        
        print(f"[Files] Uploaded: {object_name} ({len(content)} bytes) by {key_name}")
        
        return FileUploadResponse(
            name=file.filename,
            path=object_name,
            size=len(content),
            bucket=bucket,
            etag=result.etag,
        )
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/v1/files/download/{file_path:path}", tags=["Files"])
async def download_file(
    file_path: str,
    bucket: str = Query(default=""),
    key_name: str = Depends(verify_api_key),
):
    """
    Download a file from MinIO storage.
    
    - **file_path**: Full path to the file within the bucket
    - **bucket**: Source bucket (defaults to personal-files)
    """
    if not minio_client:
        raise HTTPException(status_code=503, detail="MinIO not available")
    
    bucket = bucket or config.MINIO_DEFAULT_BUCKET
    
    try:
        response = minio_client.get_object(bucket, file_path)
        
        # Determine content type
        stat = minio_client.stat_object(bucket, file_path)
        content_type = stat.content_type or "application/octet-stream"
        filename = file_path.split("/")[-1]
        
        print(f"[Files] Downloaded: {file_path} by {key_name}")
        
        return StreamingResponse(
            response,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(stat.size),
            }
        )
    except S3Error as e:
        if e.code == "NoSuchKey":
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@app.get(
    "/v1/files/list",
    response_model=FileListResponse,
    tags=["Files"],
)
async def list_files(
    prefix: str = Query(default="", description="Filter by path prefix"),
    bucket: str = Query(default=""),
    key_name: str = Depends(verify_api_key),
):
    """
    List files in MinIO storage.
    
    - **prefix**: Optional path prefix filter (e.g. 'projects/' to list all project files)
    - **bucket**: Target bucket (defaults to personal-files)
    """
    if not minio_client:
        raise HTTPException(status_code=503, detail="MinIO not available")
    
    bucket = bucket or config.MINIO_DEFAULT_BUCKET
    
    try:
        objects = minio_client.list_objects(bucket, prefix=prefix or None, recursive=True)
        
        files = []
        for obj in objects:
            files.append(FileInfo(
                name=obj.object_name.split("/")[-1] if "/" in obj.object_name else obj.object_name,
                path=obj.object_name,
                size=obj.size or 0,
                content_type=obj.content_type or "",
                last_modified=obj.last_modified,
                etag=obj.etag or "",
                bucket=bucket,
            ))
        
        return FileListResponse(
            files=files,
            total=len(files),
            prefix=prefix,
            bucket=bucket,
        )
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"List failed: {str(e)}")


@app.delete(
    "/v1/files/{file_path:path}",
    response_model=FileDeleteResponse,
    tags=["Files"],
)
async def delete_file(
    file_path: str,
    bucket: str = Query(default=""),
    key_name: str = Depends(verify_api_key),
):
    """Delete a file from MinIO storage."""
    if not minio_client:
        raise HTTPException(status_code=503, detail="MinIO not available")
    
    bucket = bucket or config.MINIO_DEFAULT_BUCKET
    
    try:
        # Check file exists
        minio_client.stat_object(bucket, file_path)
        minio_client.remove_object(bucket, file_path)
        
        print(f"[Files] Deleted: {file_path} by {key_name}")
        
        return FileDeleteResponse(
            name=file_path.split("/")[-1],
            path=file_path,
        )
    except S3Error as e:
        if e.code == "NoSuchKey":
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


# ─── Context API ─────────────────────────────────────────────

@app.post(
    "/v1/context/save",
    response_model=ContextSaveResponse,
    tags=["Context"],
)
async def save_context(
    context: AgentContext,
    key_name: str = Depends(verify_api_key),
):
    """
    Save an agent context for cross-tool synchronization.
    
    This is the primary endpoint for persisting work state when switching
    between different AI agent tools (Cursor, Codex, Antigravity, etc.).
    
    If a context with the same session_id exists, it will be updated
    (with automatic backup of the previous version).
    """
    result = context_manager.save(context)
    print(f"[Context] Saved: {context.session_id} (project={context.project}) by {key_name}")
    
    return ContextSaveResponse(
        session_id=context.session_id,
        project=context.project,
    )


@app.get(
    "/v1/context/{session_id}",
    response_model=AgentContext,
    tags=["Context"],
)
async def get_context(
    session_id: str,
    key_name: str = Depends(verify_api_key),
):
    """Load a specific agent context by session ID."""
    ctx = context_manager.load(session_id)
    if not ctx:
        raise HTTPException(status_code=404, detail=f"Context not found: {session_id}")
    return ctx


@app.get(
    "/v1/context/latest/{project}",
    response_model=AgentContext,
    tags=["Context"],
)
async def get_latest_context(
    project: str,
    agent_tool: Optional[str] = Query(default=None, description="Filter by agent tool"),
    key_name: str = Depends(verify_api_key),
):
    """
    Get the most recently updated context for a project.
    
    Use this when resuming work in a new agent tool:
    1. Call this endpoint to get the latest context
    2. Read the 'summary' field to understand current work state
    3. Continue from where the previous agent left off
    """
    ctx = context_manager.get_latest(project, agent_tool)
    if not ctx:
        raise HTTPException(
            status_code=404,
            detail=f"No context found for project: {project}"
        )
    return ctx


@app.get(
    "/v1/context/list",
    response_model=ContextListResponse,
    tags=["Context"],
)
async def list_contexts(
    project: Optional[str] = Query(default=None),
    agent_tool: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    key_name: str = Depends(verify_api_key),
):
    """List agent contexts with optional filtering."""
    contexts, total = context_manager.list_contexts(
        project=project,
        agent_tool=agent_tool,
        limit=limit,
        offset=offset,
    )
    return ContextListResponse(contexts=contexts, total=total)


@app.delete(
    "/v1/context/{session_id}",
    tags=["Context"],
)
async def delete_context(
    session_id: str,
    key_name: str = Depends(verify_api_key),
):
    """Delete an agent context."""
    if not context_manager.delete(session_id):
        raise HTTPException(status_code=404, detail=f"Context not found: {session_id}")
    
    print(f"[Context] Deleted: {session_id} by {key_name}")
    return {"message": f"Context {session_id} deleted"}


@app.post(
    "/v1/context/{session_id}/log",
    tags=["Context"],
)
async def append_context_log(
    session_id: str,
    log_entry: dict,
    key_name: str = Depends(verify_api_key),
):
    """
    Append a raw conversation log entry to a context's JSONL log file.
    Use this for streaming full conversation history.
    """
    # Look up project from index
    entry = context_manager.index["contexts"].get(session_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Context not found: {session_id}")
    
    path = context_manager.append_raw_log(entry["project"], session_id, log_entry)
    return {"message": "Log entry appended", "path": path}


@app.get("/v1/context/stats", tags=["Context"])
async def context_stats(key_name: str = Depends(verify_api_key)):
    """Get storage statistics for all contexts."""
    return context_manager.get_storage_stats()


# ─── Agent Bootstrap API ─────────────────────────────────────

@app.get("/v1/index/projects", tags=["Agent Bootstrap"])
async def list_index_projects(key_name: str = Depends(verify_api_key)):
    """List indexed project profiles."""
    index, _, _, _, _ = require_agent_cloud_services()
    return {"projects": [project.model_dump() for project in index.list_projects()]}


@app.post("/v1/index/projects", response_model=ProjectProfile, tags=["Agent Bootstrap"])
async def upsert_index_project(
    profile: ProjectProfile,
    key_name: str = Depends(verify_api_key),
):
    """Create or update a project profile in the lightweight index."""
    index, _, _, _, _ = require_agent_cloud_services()
    return index.upsert_project(profile)


@app.post("/v1/index/search", response_model=IndexSearchResponse, tags=["Agent Bootstrap"])
async def search_index(
    request: IndexSearchRequest,
    key_name: str = Depends(verify_api_key),
):
    """Search projects using metadata fields."""
    index, _, _, _, _ = require_agent_cloud_services()
    return IndexSearchResponse(
        candidates=index.search(
            project_id=request.project_id,
            git_remote=request.git_remote,
            path_fingerprint=request.path_fingerprint,
            query=request.query,
            limit=request.limit,
        )
    )


@app.get("/v1/rules/current", tags=["Agent Bootstrap"])
async def get_current_rules(key_name: str = Depends(verify_api_key)):
    """Return canonical Markdown and machine-readable rules."""
    _, rules, _, _, _ = require_agent_cloud_services()
    return rules.current()


@app.get("/v1/rules/render", tags=["Agent Bootstrap"])
async def render_rules(
    profile: str = Query(default="default-agent-project"),
    agent: str = Query(default="generic"),
    key_name: str = Depends(verify_api_key),
):
    """Render Markdown rules for an agent/profile pair."""
    _, rules, _, _, _ = require_agent_cloud_services()
    return {"markdown": rules.render(profile=profile, agent=agent)}


@app.get("/v1/skills/registry", tags=["Agent Bootstrap"])
async def get_skills_registry(key_name: str = Depends(verify_api_key)):
    """Return the remote-readable skill registry."""
    _, _, skills, _, _ = require_agent_cloud_services()
    return skills.registry()


@app.get("/v1/skills/{skill_id}/read", tags=["Agent Bootstrap"])
async def read_skill(skill_id: str, key_name: str = Depends(verify_api_key)):
    """Read a remote skill document by ID."""
    _, _, skills, _, _ = require_agent_cloud_services()
    try:
        manifest = skills.manifest(skill_id)
        content = skills.read_skill(skill_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
    return {"skill_id": skill_id, "manifest": manifest, "content": content}


@app.post("/v1/bootstrap", response_model=BootstrapResponse, tags=["Agent Bootstrap"])
async def bootstrap_agent(
    request: BootstrapRequest,
    key_name: str = Depends(verify_api_key),
):
    """Return a minimal bootstrap package for a new Agent session."""
    _, _, _, service, _ = require_agent_cloud_services()
    return service.bootstrap(request)


@app.get("/v1/setup/prompt", tags=["Agent Bootstrap"])
async def generate_setup_prompt(
    agent_name: str = Query(default="generic"),
    default_project_id: str = Query(default=""),
    base_url: str = Query(default=""),
    key_name: str = Depends(verify_api_key),
):
    """Generate a copyable setup prompt for a new Agent."""
    _, _, _, _, generator = require_agent_cloud_services()
    return {
        "prompt": generator.generate_prompt(
            base_url=base_url or config.PUBLIC_BASE_URL,
            agent_name=agent_name,
            default_project_id=default_project_id,
        )
    }


@app.get("/v1/setup/package", tags=["Agent Bootstrap"])
async def generate_setup_package(
    agent_name: str = Query(default="generic"),
    default_project_id: str = Query(default=""),
    base_url: str = Query(default=""),
    key_name: str = Depends(verify_api_key),
):
    """Generate and download a non-secret setup package archive."""
    _, _, _, _, generator = require_agent_cloud_services()
    path = generator.generate_package(
        output_dir=config.SETUP_PACKAGES_DIR,
        base_url=base_url or config.PUBLIC_BASE_URL,
        agent_name=agent_name,
        default_project_id=default_project_id,
    )
    return FileResponse(path, filename=path.name, media_type="application/zip")


@app.get("/v1/tests/smoke", tags=["Tests"])
async def run_smoke_tests(key_name: str = Depends(verify_api_key)):
    """Return a smoke test report for the Web console."""
    return SmokeTestRunner().run_static_checks()


# ─── Bucket Management ───────────────────────────────────────

@app.post("/v1/buckets/{bucket_name}", tags=["Admin"])
async def create_bucket(
    bucket_name: str,
    key_name: str = Depends(verify_api_key),
):
    """Create a new MinIO bucket."""
    if not minio_client:
        raise HTTPException(status_code=503, detail="MinIO not available")
    
    try:
        if minio_client.bucket_exists(bucket_name):
            return {"message": f"Bucket '{bucket_name}' already exists"}
        
        minio_client.make_bucket(bucket_name)
        print(f"[Admin] Created bucket: {bucket_name} by {key_name}")
        return {"message": f"Bucket '{bucket_name}' created"}
    except S3Error as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/buckets", tags=["Admin"])
async def list_buckets(key_name: str = Depends(verify_api_key)):
    """List all MinIO buckets."""
    if not minio_client:
        raise HTTPException(status_code=503, detail="MinIO not available")
    
    buckets = minio_client.list_buckets()
    return {
        "buckets": [
            {"name": b.name, "created": str(b.creation_date)}
            for b in buckets
        ]
    }


# ─── Error Handlers ──────────────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "detail": str(exc.detail) if hasattr(exc, 'detail') else ""},
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# ─── Entry Point ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=False,
        log_level="info",
    )
