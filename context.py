"""
Agent Context Manager.
Handles CRUD operations for agent conversation contexts.
Stores contexts as JSON files on the filesystem.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

import config
from index_store import IndexStore
from models import AgentContext


class ContextManager:
    """
    Manages agent context persistence.
    
    Directory structure:
        /workspace/cloud/contexts/
        ├── {project}/
        │   ├── {session_id}.json          # Structured context
        │   ├── {session_id}.raw.jsonl     # Raw conversation log (optional)
        │   └── ...
        └── _index.json                    # Quick lookup index
    """
    
    def __init__(
        self,
        base_dir: Optional[Path] = None,
        index_store: Optional[IndexStore] = None,
    ):
        self.base_dir = base_dir or config.CONTEXT_DIR
        self.index_store = index_store
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.base_dir / "_index.json"
        self._load_index()
    
    def _load_index(self):
        """Load or create the context index."""
        if self.index_file.exists():
            with open(self.index_file, "r", encoding="utf-8") as f:
                self.index = json.load(f)
        else:
            self.index = {"contexts": {}}
            self._save_index()
    
    def _save_index(self):
        """Persist the index to disk."""
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self.index, f, indent=2, ensure_ascii=False, default=str)
    
    def _context_path(self, project: str, session_id: str) -> Path:
        """Get the file path for a context."""
        project_dir = self.base_dir / self._sanitize(project)
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir / f"{session_id}.json"
    
    def _raw_log_path(self, project: str, session_id: str) -> Path:
        """Get the file path for raw conversation log."""
        project_dir = self.base_dir / self._sanitize(project)
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir / f"{session_id}.raw.jsonl"
    
    @staticmethod
    def _sanitize(name: str) -> str:
        """Sanitize project/session names for safe filesystem paths."""
        # Replace dangerous characters
        for char in ['..', '/', '\\', '\0', '~']:
            name = name.replace(char, '_')
        return name.strip('._')
    
    def save(self, context: AgentContext) -> dict:
        """
        Save an agent context. If a context with the same session_id exists,
        it will be overwritten (with a backup kept).
        """
        context.updated_at = datetime.utcnow()
        path = self._context_path(context.project, context.session_id)
        
        # Create backup of existing context
        if path.exists():
            backup_dir = path.parent / "_backups"
            backup_dir.mkdir(exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{context.session_id}_{timestamp}.json"
            shutil.copy2(path, backup_path)
            
            # Clean old backups (keep last N)
            backups = sorted(backup_dir.glob(f"{context.session_id}_*.json"))
            for old_backup in backups[:-config.CONTEXT_BACKUP_COUNT]:
                old_backup.unlink()
        
        # Save context
        with open(path, "w", encoding="utf-8") as f:
            json.dump(context.model_dump(), f, indent=2, ensure_ascii=False, default=str)
        
        # Update index
        self.index["contexts"][context.session_id] = {
            "project": context.project,
            "agent_tool": context.agent_tool,
            "summary": context.summary[:200],  # Truncate for index
            "updated_at": str(context.updated_at),
            "created_at": str(context.created_at),
        }
        self._save_index()
        if self.index_store:
            self.index_store.update_context(context)
        
        return {
            "session_id": context.session_id,
            "project": context.project,
            "path": str(path),
        }
    
    def load(self, session_id: str, project: Optional[str] = None) -> Optional[AgentContext]:
        """
        Load a context by session_id.
        If project is not specified, look it up from the index.
        """
        if not project:
            entry = self.index["contexts"].get(session_id)
            if not entry:
                return None
            project = entry["project"]
        
        path = self._context_path(project, session_id)
        if not path.exists():
            return None
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return AgentContext(**data)
    
    def get_latest(self, project: str, agent_tool: Optional[str] = None) -> Optional[AgentContext]:
        """
        Get the most recently updated context for a project.
        Optionally filter by agent tool.
        """
        candidates = []
        for sid, entry in self.index["contexts"].items():
            if entry["project"] == project:
                if agent_tool and entry.get("agent_tool") != agent_tool:
                    continue
                candidates.append((sid, entry))
        
        if not candidates:
            return None
        
        # Sort by updated_at descending
        candidates.sort(key=lambda x: x[1].get("updated_at", ""), reverse=True)
        latest_sid = candidates[0][0]
        
        return self.load(latest_sid, project)
    
    def list_contexts(
        self, 
        project: Optional[str] = None,
        agent_tool: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AgentContext], int]:
        """
        List contexts with optional filtering.
        Returns (contexts, total_count).
        """
        # Filter from index
        filtered = []
        for sid, entry in self.index["contexts"].items():
            if project and entry["project"] != project:
                continue
            if agent_tool and entry.get("agent_tool") != agent_tool:
                continue
            filtered.append((sid, entry))
        
        # Sort by updated_at descending
        filtered.sort(key=lambda x: x[1].get("updated_at", ""), reverse=True)
        total = len(filtered)
        
        # Paginate
        page = filtered[offset:offset + limit]
        
        # Load full contexts
        contexts = []
        for sid, entry in page:
            ctx = self.load(sid, entry["project"])
            if ctx:
                contexts.append(ctx)
        
        return contexts, total
    
    def delete(self, session_id: str) -> bool:
        """Delete a context and its backups."""
        entry = self.index["contexts"].get(session_id)
        if not entry:
            return False
        
        project = entry["project"]
        path = self._context_path(project, session_id)
        raw_path = self._raw_log_path(project, session_id)
        
        # Delete files
        if path.exists():
            path.unlink()
        if raw_path.exists():
            raw_path.unlink()
        
        # Delete backups
        backup_dir = path.parent / "_backups"
        if backup_dir.exists():
            for backup in backup_dir.glob(f"{session_id}_*.json"):
                backup.unlink()
        
        # Remove from index
        del self.index["contexts"][session_id]
        self._save_index()
        
        return True
    
    def append_raw_log(self, project: str, session_id: str, log_entry: dict) -> str:
        """
        Append a raw conversation log entry (JSONL format).
        Used for storing complete conversation history.
        """
        log_entry["timestamp"] = log_entry.get("timestamp", datetime.utcnow().isoformat())
        path = self._raw_log_path(project, session_id)
        
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False, default=str) + "\n")
        
        return str(path)
    
    def get_storage_stats(self) -> dict:
        """Get storage statistics for all contexts."""
        total_size = 0
        file_count = 0
        
        for f in self.base_dir.rglob("*"):
            if f.is_file():
                total_size += f.stat().st_size
                file_count += 1
        
        return {
            "total_contexts": len(self.index["contexts"]),
            "total_files": file_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }
