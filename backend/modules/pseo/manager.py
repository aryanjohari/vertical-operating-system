import yaml
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class ManagerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Manager")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        user_id = input_data.user_id
        
        # 1. GET PROJECT CONTEXT
        project = memory.get_user_project(user_id)
        if not project:
            return AgentOutput(status="error", message="No active project found.")
        
        project_id = project['project_id']
        
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

        self.log(f"📊 Pipeline Status: {stats}")

        # 4. ORCHESTRATION LOGIC (Priority: Pull System - Finish what we started)
        # We check from the END of the pipeline backwards.
        
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
            message="Pipeline Balanced. Monitoring...",
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
        
        self.log(f"🚀 Executing task: {task_name} ({step_labels.get(step_id, step_id)})")
        
        # Create AgentInput for the task
        task_input = AgentInput(
            task=task_name,
            user_id=user_id,
            params=params
        )
        
        # Execute the task via kernel
        try:
            task_result = await kernel.dispatch(task_input)
            
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
        except Exception as e:
            self.log(f"❌ Error executing task {task_name}: {e}")
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
    
    def _format_stats(self, stats):
        return {
            "Locations": stats["anchors"],
            "Keywords": stats["kws_total"],
            "Drafts": stats["1_unreviewed"] + stats["2_validated"] + stats["3_linked"] + stats["4_imaged"] + stats["5_ready"] + stats["6_live"],
            "1_unreviewed": stats["1_unreviewed"],
            "2_validated": stats["2_validated"],
            "3_linked": stats["3_linked"],
            "4_imaged": stats["4_imaged"],
            "5_ready": stats["5_ready"],
            "6_live": stats["6_live"],
            "kws_pending": stats["kws_pending"],
        }