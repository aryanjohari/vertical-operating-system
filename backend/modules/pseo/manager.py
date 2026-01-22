import yaml
import asyncio
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class ManagerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Manager")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        # Validate injected context (Titanium Standard)
        if not self.project_id or not self.user_id:
            self.logger.error("Missing injected context: project_id or user_id")
            return AgentOutput(status="error", message="Agent context not properly initialized.")
        
        project_id = self.project_id
        user_id = self.user_id
        
        # Verify project ownership (security: defense-in-depth)
        if not memory.verify_project_ownership(user_id, project_id):
            self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
            return AgentOutput(status="error", message="Project not found or access denied.")
        
        # Get action parameter (default to dashboard_stats for stats-only mode)
        action = input_data.params.get("action", "dashboard_stats")
        
        # 2. FETCH ASSETS (Scoped to Project)
        anchors = memory.get_entities(tenant_id=user_id, entity_type="anchor_location", project_id=project_id)
        kws = memory.get_entities(tenant_id=user_id, entity_type="seo_keyword", project_id=project_id)
        drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        
        # 3. CALCULATE PIPELINE STATS
        stats = {
            "anchors": len(anchors),
            "kws_total": len(kws),
            "kws_pending": len([k for k in kws if k['metadata'].get('status') == 'pending']),
            
            # PIPELINE STAGES
            "1_unreviewed": len([d for d in drafts if d['metadata'].get('status') == 'draft']),
            "2_validated": len([d for d in drafts if d['metadata'].get('status') == 'validated']),
            "3_linked": len([d for d in drafts if d['metadata'].get('status') == 'ready_for_media']),
            "4_imaged": len([d for d in drafts if d['metadata'].get('status') == 'ready_for_utility']),
            "5_ready": len([d for d in drafts if d['metadata'].get('status') == 'ready_to_publish']),
            "6_live": len([d for d in drafts if d['metadata'].get('status') in ['published', 'live']])
        }

        self.logger.info(f"📊 Pipeline Status: {stats}")

        # 4. ACTION-BASED ROUTING
        if action == "dashboard_stats":
            # Return stats only, no orchestration
            # Also include recommended next step
            next_step = self._get_recommended_next_step(stats)
            return AgentOutput(
                status="success",
                message="Stats retrieved",
                data={
                    "stats": self._format_stats(stats),
                    "next_step": next_step
                }
            )
        elif action == "auto_orchestrate":
            # Run orchestration logic (only when explicitly triggered)
            return await self._run_orchestration(stats, user_id, project_id)
        else:
            # Unknown action, return stats
            self.logger.warning(f"Unknown action: {action}, returning stats")
            return AgentOutput(
                status="success",
                message="Stats retrieved",
                data={
                    "stats": self._format_stats(stats)
                }
            )

    async def _run_orchestration(self, stats: dict, user_id: str, project_id: str) -> AgentOutput:
        """
        Orchestration Logic (Priority: Pull System - Finish what we started)
        Only runs when explicitly triggered via action="auto_orchestrate"
        We check from the END of the pipeline backwards.
        """
        self.logger.info("🔄 Running pipeline orchestration...")
        
        # Phase 8: Publishing (Clear the exit)
        if stats["5_ready"] > 0:
            return await self._execute_task("publish", "8_publisher", {"limit": 2}, stats, user_id, project_id)

        # Phase 7: Lead Gen (Add Tools)
        if stats["4_imaged"] > 0:
            return await self._execute_task("enhance_utility", "7_utility", {}, stats, user_id, project_id)

        # Phase 6: Visuals (Add Images)
        if stats["3_linked"] > 0:
            return await self._execute_task("enhance_media", "6_media", {}, stats, user_id, project_id)

        # Phase 5: Internal Linking (Librarian)
        if stats["2_validated"] > 0:
            return await self._execute_task("librarian_link", "5_librarian", {}, stats, user_id, project_id)

        # Phase 4: Quality Control (Critic)
        if stats["1_unreviewed"] > 0:
            return await self._execute_task("critic_review", "4_critic", {}, stats, user_id, project_id)

        # Phase 3: Drafting (Writer)
        # Rule: Only write if downstream is clear AND buffer < 2
        if stats["kws_pending"] > 0 and stats["1_unreviewed"] < 2:
            return await self._execute_task("write_pages", "3_writer", {}, stats, user_id, project_id)

        # Phase 2: Strategy (Get Keywords)
        if stats["kws_total"] < (stats["anchors"] * 5) and stats["anchors"] > 0:
            return await self._execute_task("strategist_run", "2_strategy", {}, stats, user_id, project_id)

        # Phase 1: Context (Scout)
        if stats["anchors"] == 0:
            return await self._execute_task("scout_anchors", "1_scout", {"queries": ["district court", "prison"]}, stats, user_id, project_id)

        # Phase 9: Feedback Loop (Analytics)
        if stats["6_live"] > 20:
            return await self._execute_task("analytics_audit", "9_analytics", {}, stats, user_id, project_id)

        # Pipeline balanced
        return AgentOutput(
            status="complete",
            message="Pipeline Balanced. No actions needed.",
            data={
                "step": "complete",
                "action_label": "System Idle",
                "stats": self._format_stats(stats)
            }
        )

    async def _execute_task(self, task_name: str, step_id: str, params: dict, stats: dict, user_id: str, project_id: str) -> AgentOutput:
        """
        Executes the recommended task directly via kernel dispatch.
        
        Data Flow:
        1. Manager determines which task needs to run
        2. Manager creates AgentInput and dispatches via kernel
        3. Kernel routes to the appropriate agent
        4. Agent executes and returns AgentOutput
        5. Manager wraps the result with context and returns to frontend
        """
        # Lazy import to avoid circular dependency during kernel initialization
        from backend.core.kernel import kernel
        
        step_labels = {
            "1_scout": "Scouting Locations",
            "2_strategy": "Generating Keywords",
            "3_writer": "Writing Pages",
            "4_critic": "Reviewing Quality",
            "5_librarian": "Adding Links",
            "6_media": "Fetching Images",
            "7_utility": "Building Tools",
            "8_publisher": "Publishing Content",
            "9_analytics": "Analyzing Performance"
        }
        
        # Explicitly pass project_id and user_id in params for downstream agents
        params['project_id'] = project_id
        params['user_id'] = user_id
        
        self.logger.info(f"🚀 Executing task: {task_name} ({step_labels.get(step_id, step_id)})")
        
        # Create AgentInput for the task
        task_input = AgentInput(
            task=task_name,
            user_id=user_id,
            params=params
        )
        
        # Execute the task via kernel (with timeout to prevent deadlock)
        try:
            task_result = await asyncio.wait_for(
                kernel.dispatch(task_input),
                timeout=300  # 5 minutes max per task
            )
            
            # Return result with manager context
            return AgentOutput(
                status=task_result.status,
                message=f"Executed {step_labels.get(step_id, step_id)}: {task_result.message}",
                data={
                    "step": step_id,
                    "action_label": step_labels.get(step_id, step_id),
                    "task_executed": task_name,
                    "task_result": task_result.dict(),
                    "stats": self._format_stats(stats)
                }
            )
        except asyncio.TimeoutError:
            self.logger.error(f"❌ Task {task_name} timed out after 5 minutes")
            return AgentOutput(
                status="error",
                message=f"Task execution timed out after 5 minutes.",
                data={
                    "step": step_id,
                    "action_label": step_labels.get(step_id, step_id),
                    "task_executed": task_name,
                    "error": "Task timeout",
                    "stats": self._format_stats(stats)
                }
            )
        except Exception as e:
            self.logger.error(f"❌ Error executing task {task_name}: {e}", exc_info=True)
            return AgentOutput(
                status="error",
                message=f"Failed to execute {step_labels.get(step_id, step_id)}: {str(e)}",
                data={
                    "step": step_id,
                    "action_label": step_labels.get(step_id, step_id),
                    "task_executed": task_name,
                    "error": str(e),
                    "stats": self._format_stats(stats)
                }
            )
    
    def _get_recommended_next_step(self, stats: dict) -> dict:
        """
        Determine the recommended next step based on pipeline status.
        Returns: { agent_key, label, description, reason }
        """
        # Phase 8: Publishing (Clear the exit)
        if stats["5_ready"] > 0:
            return {
                "agent_key": "publish",
                "label": "Publisher",
                "description": "Publish ready content",
                "reason": f"{stats['5_ready']} pages ready to publish"
            }

        # Phase 7: Lead Gen (Add Tools)
        if stats["4_imaged"] > 0:
            return {
                "agent_key": "enhance_utility",
                "label": "Utility",
                "description": "Build lead magnets",
                "reason": f"{stats['4_imaged']} pages need tools"
            }

        # Phase 6: Visuals (Add Images)
        if stats["3_linked"] > 0:
            return {
                "agent_key": "enhance_media",
                "label": "Media",
                "description": "Add images",
                "reason": f"{stats['3_linked']} pages need images"
            }

        # Phase 5: Internal Linking (Librarian)
        if stats["2_validated"] > 0:
            return {
                "agent_key": "librarian_link",
                "label": "Librarian",
                "description": "Add internal links",
                "reason": f"{stats['2_validated']} pages need links"
            }

        # Phase 4: Quality Control (Critic)
        if stats["1_unreviewed"] > 0:
            return {
                "agent_key": "critic_review",
                "label": "Critic",
                "description": "Quality check",
                "reason": f"{stats['1_unreviewed']} drafts need review"
            }

        # Phase 3: Drafting (Writer)
        if stats["kws_pending"] > 0 and stats["1_unreviewed"] < 2:
            return {
                "agent_key": "write_pages",
                "label": "Writer",
                "description": "Create content",
                "reason": f"{stats['kws_pending']} keywords need pages"
            }

        # Phase 2: Strategy (Get Keywords)
        if stats["kws_total"] < (stats["anchors"] * 5) and stats["anchors"] > 0:
            return {
                "agent_key": "strategist_run",
                "label": "Strategist",
                "description": "Generate keywords",
                "reason": f"Need more keywords ({stats['kws_total']}/{stats['anchors'] * 5})"
            }

        # Phase 1: Context (Scout)
        if stats["anchors"] == 0:
            return {
                "agent_key": "scout_anchors",
                "label": "Scout",
                "description": "Find locations",
                "reason": "No anchor locations found"
            }

        # Phase 9: Feedback Loop (Analytics)
        if stats["6_live"] > 20:
            return {
                "agent_key": "analytics_audit",
                "label": "Analytics",
                "description": "Analyze performance",
                "reason": f"{stats['6_live']} live pages ready for analysis"
            }

        # Pipeline balanced
        return {
            "agent_key": None,
            "label": "Pipeline Balanced",
            "description": "All stages are progressing well",
            "reason": "No immediate action needed"
        }

    def _format_stats(self, stats):
        return {
            "anchors": stats["anchors"],
            "kws_total": stats["kws_total"],
            "Drafts": stats["1_unreviewed"] + stats["2_validated"] + stats["3_linked"] + stats["4_imaged"] + stats["5_ready"] + stats["6_live"],
            "1_unreviewed": stats["1_unreviewed"],
            "2_validated": stats["2_validated"],
            "3_linked": stats["3_linked"],
            "4_imaged": stats["4_imaged"],
            "5_ready": stats["5_ready"],
            "6_live": stats["6_live"],
            "kws_pending": stats["kws_pending"],
        }