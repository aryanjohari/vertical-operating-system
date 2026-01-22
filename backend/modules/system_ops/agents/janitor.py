# backend/modules/system_ops/agents/janitor.py
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput

class JanitorAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="JanitorAgent")
        self.logger = logging.getLogger("Apex.Janitor")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Cleans up old files from logs and downloads directories.
        
        Logic:
        - Scans data/logs/ and deletes files older than 30 days
        - Scans downloads/ and deletes files older than 24 hours
        """
        self.logger.info("🧹 Starting cleanup operation...")
        
        deleted_files = []
        total_size_freed = 0
        
        # Get base directory (project root)
        base_dir = Path(__file__).parent.parent.parent.parent.parent
        
        # 1. Clean logs directory (30 days)
        logs_dir = base_dir / "logs"
        if logs_dir.exists() and logs_dir.is_dir():
            deleted_count, size_freed = self._clean_directory(logs_dir, days=30)
            deleted_files.extend([f"logs/{f}" for f in deleted_count])
            total_size_freed += size_freed
            self.logger.info(f"✅ Cleaned logs: {len(deleted_count)} files, {size_freed / (1024*1024):.2f} MB freed")
        else:
            self.logger.debug("⚠️ Logs directory not found, skipping")
        
        # 2. Clean downloads directory (24 hours)
        downloads_dir = base_dir / "downloads"
        if downloads_dir.exists() and downloads_dir.is_dir():
            deleted_count, size_freed = self._clean_directory(downloads_dir, days=1)
            deleted_files.extend([f"downloads/{f}" for f in deleted_count])
            total_size_freed += size_freed
            self.logger.info(f"✅ Cleaned downloads: {len(deleted_count)} files, {size_freed / (1024*1024):.2f} MB freed")
        else:
            self.logger.debug("⚠️ Downloads directory not found, skipping")
        
        return AgentOutput(
            status="success",
            data={
                "files_deleted": len(deleted_files),
                "size_freed_mb": round(total_size_freed / (1024 * 1024), 2),
                "deleted_files": deleted_files[:10]  # Limit to first 10 for response size
            },
            message=f"Cleanup complete. Deleted {len(deleted_files)} files, freed {total_size_freed / (1024*1024):.2f} MB"
        )
    
    def _clean_directory(self, directory: Path, days: int) -> tuple:
        """
        Cleans a directory by deleting files older than specified days.
        
        Returns:
            (list of deleted filenames, total size freed in bytes)
        """
        deleted_files = []
        total_size = 0
        cutoff_time = datetime.now() - timedelta(days=days)
        
        try:
            for item in directory.iterdir():
                # Only process files, not directories
                if not item.is_file():
                    continue
                
                try:
                    # Get file modification time
                    mtime = datetime.fromtimestamp(item.stat().st_mtime)
                    
                    if mtime < cutoff_time:
                        file_size = item.stat().st_size
                        item.unlink()
                        deleted_files.append(item.name)
                        total_size += file_size
                        self.logger.debug(f"🗑️ Deleted: {item.name} (age: {(datetime.now() - mtime).days} days)")
                except OSError as e:
                    self.logger.warning(f"⚠️ Failed to delete {item.name}: {e}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Error processing {item.name}: {e}")
        
        except Exception as e:
            self.logger.error(f"❌ Error cleaning directory {directory}: {e}", exc_info=True)
        
        return deleted_files, total_size
