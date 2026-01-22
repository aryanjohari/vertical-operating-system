# backend/modules/system_ops/agents/sentinel.py
import logging
import os
import shutil
import httpx
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.modules.system_ops.models import SystemHealthStatus

class SentinelAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="SentinelAgent")
        self.logger = logging.getLogger("Apex.Sentinel")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Performs comprehensive health checks on the system.
        
        Checks:
        1. Internet connectivity (Google ping)
        2. Disk space availability
        3. Twilio API connectivity
        4. Database connectivity
        """
        self.logger.info("🔍 Starting system health check...")
        
        health_status = SystemHealthStatus(
            status="healthy",
            database_ok=False,
            twilio_ok=False,
            gemini_ok=False,
            disk_space_ok=False
        )
        
        # 1. Check Internet Connectivity (Google)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("https://www.google.com", follow_redirects=True)
                if response.status_code == 200:
                    self.logger.debug("✅ Internet connectivity: OK")
                else:
                    self.logger.warning(f"⚠️ Internet connectivity: Unexpected status {response.status_code}")
        except Exception as e:
            self.logger.error(f"❌ Internet connectivity check failed: {e}")
            health_status.status = "critical"
        
        # 2. Check Disk Space
        try:
            disk_usage = shutil.disk_usage("/")
            free_gb = disk_usage.free / (1024 ** 3)  # Convert to GB
            
            if free_gb < 1.0:
                self.logger.error(f"🚨 CRITICAL: Disk space below 1GB! Free: {free_gb:.2f} GB")
                health_status.status = "critical"
                health_status.disk_space_ok = False
            else:
                self.logger.debug(f"✅ Disk space: {free_gb:.2f} GB free")
                health_status.disk_space_ok = True
        except Exception as e:
            self.logger.error(f"❌ Disk space check failed: {e}")
            health_status.status = "critical"
        
        # 3. Check Twilio API
        try:
            twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
            twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
            
            if not twilio_sid or not twilio_token:
                self.logger.warning("⚠️ Twilio credentials not configured, skipping check")
                health_status.twilio_ok = False
            else:
                from twilio.rest import Client
                twilio_client = Client(twilio_sid, twilio_token)
                # Try to fetch account info (lightweight API call)
                account = twilio_client.api.accounts(twilio_sid).fetch()
                if account:
                    self.logger.debug("✅ Twilio API: OK")
                    health_status.twilio_ok = True
        except Exception as e:
            self.logger.warning(f"⚠️ Twilio API check failed: {e}")
            health_status.twilio_ok = False
        
        # 4. Check Database
        try:
            # Try a simple read operation
            conn = None
            try:
                import sqlite3
                conn = sqlite3.connect(memory.db_path)
                cursor = conn.execute("SELECT 1")
                cursor.fetchone()
                self.logger.debug("✅ Database: OK")
                health_status.database_ok = True
            finally:
                if conn:
                    conn.close()
        except Exception as e:
            self.logger.error(f"❌ Database check failed: {e}")
            health_status.status = "critical"
            health_status.database_ok = False
        
        # 5. Check Gemini API (optional, but good to know)
        try:
            gemini_key = os.getenv("GOOGLE_API_KEY")
            if not gemini_key:
                self.logger.debug("⚠️ Google API key not configured, skipping Gemini check")
                health_status.gemini_ok = False
            else:
                # Just check if the key exists, actual API call would cost tokens
                # For now, we'll assume if key exists, it's OK
                health_status.gemini_ok = True
                self.logger.debug("✅ Gemini API: Key configured")
        except Exception as e:
            self.logger.warning(f"⚠️ Gemini API check failed: {e}")
            health_status.gemini_ok = False
        
        # Final status determination
        if health_status.status == "critical":
            self.logger.error("🚨🚨🚨 SYSTEM HEALTH: CRITICAL 🚨🚨🚨")
            self.logger.error(f"Database: {'OK' if health_status.database_ok else 'FAILED'}")
            self.logger.error(f"Disk Space: {'OK' if health_status.disk_space_ok else 'CRITICAL'}")
            self.logger.error(f"Twilio: {'OK' if health_status.twilio_ok else 'FAILED'}")
            # Future: Send SMS alert here
        
        return AgentOutput(
            status="success",
            data=health_status.dict(),
            message=f"Health check complete. Status: {health_status.status.upper()}"
        )
