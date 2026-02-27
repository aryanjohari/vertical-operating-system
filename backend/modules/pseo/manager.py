# backend/modules/pseo/manager.py
import asyncio
from typing import Dict, Any, Optional
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.config import settings
from backend.core.memory import memory


class ManagerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Manager")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        # Titanium Standard: Validate injected context
        if not self.project_id or not self.user_id:
            self.logger.error("Missing injected context: project_id or user_id")
            return AgentOutput(status="error", message="Agent context not properly initialized.")

        project_id = self.project_id
        user_id = self.user_id
        campaign_id = input_data.params.get("campaign_id") or self.campaign_id

        if not campaign_id:
            return AgentOutput(status="error", message="campaign_id is required. Please create a campaign first or provide campaign_id in params.")

        if not memory.verify_project_ownership(user_id, project_id):
            self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
            return AgentOutput(status="error", message="Project not found or access denied.")

        campaign = memory.get_campaign(campaign_id, user_id)
        if not campaign:
            return AgentOutput(status="error", message="Campaign not found or access denied.")
        if campaign.get("module") != "pseo":
            return AgentOutput(status="error", message=f"Campaign {campaign_id} is not a pSEO campaign.")
        if not self.config.get("modules", {}).get("local_seo", {}).get("enabled", False):
            return AgentOutput(status="error", message="pSEO module is not enabled in project DNA.")

        action = input_data.params.get("action", "dashboard_stats")

        # Fetch assets (scoped to campaign)
        all_anchors = memory.get_entities(tenant_id=user_id, entity_type="anchor_location", project_id=project_id)
        all_kws = memory.get_entities(tenant_id=user_id, entity_type="seo_keyword", project_id=project_id)
        all_drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        anchors = [a for a in all_anchors if a.get("metadata", {}).get("campaign_id") == campaign_id]
        kws = [k for k in all_kws if k.get("metadata", {}).get("campaign_id") == campaign_id]
        drafts = [d for d in all_drafts if d.get("metadata", {}).get("campaign_id") == campaign_id]

        drafts_pending_writer = len([d for d in drafts if d.get("metadata", {}).get("status") == "pending_writer"])
        stats = {
            "anchors": len(anchors),
            "kws_total": len(kws),
            "kws_pending": len([k for k in kws if k.get("metadata", {}).get("status") == "pending"]),
            "drafts_pending_writer": drafts_pending_writer,
            "drafts_total": len(drafts),
            # Treat both 'draft' and 'rejected' as needing review
            "1_unreviewed": len(
                [
                    d
                    for d in drafts
                    if d.get("metadata", {}).get("status") in ("draft", "rejected")
                ]
            ),
            "2_validated": len([d for d in drafts if d.get("metadata", {}).get("status") == "validated"]),
            "3_linked": len([d for d in drafts if d.get("metadata", {}).get("status") == "ready_for_media"]),
            "4_imaged": len([d for d in drafts if d.get("metadata", {}).get("status") == "ready_for_utility"]),
            "5_ready": len([d for d in drafts if d.get("metadata", {}).get("status") == "ready_to_publish"]),
            "6_live": len([d for d in drafts if d.get("metadata", {}).get("status") in ("published", "live")]),
        }
        self.logger.info(f"Pipeline Status: {stats}")

        if action == "dashboard_stats":
            next_step = self._get_recommended_next_step(stats)
            return AgentOutput(
                status="success",
                message="Stats retrieved",
                data={"stats": self._format_stats(stats), "next_step": next_step},
            )
        if action == "pulse_stats":
            pulse = self._get_pulse_stats(stats)
            return AgentOutput(
                status="success",
                message="Pulse stats retrieved",
                data={"pulse": pulse, "stats": self._format_stats(stats)},
            )
        if action == "get_settings":
            settings = self._get_pseo_settings(campaign)
            return AgentOutput(
                status="success",
                message="PSEO settings retrieved",
                data={"settings": settings},
            )
        if action == "update_settings":
            updated = self._update_pseo_settings(
                campaign_id=campaign_id,
                user_id=user_id,
                existing_config=campaign.get("config") or {},
                params=input_data.params,
            )
            if not updated:
                return AgentOutput(
                    status="error", message="Failed to update PSEO settings."
                )
            settings = self._get_pseo_settings(
                {**campaign, "config": updated.get("config")}
            )
            return AgentOutput(
                status="success",
                message="PSEO settings updated",
                data={"settings": settings},
            )
        if action == "debug_run":
            return await self._debug_run(
                input_data=input_data,
                stats=stats,
                user_id=user_id,
                project_id=project_id,
                campaign_id=campaign_id,
            )
        if action == "intel_review":
            result = self._run_intel_review(input_data=input_data, user_id=user_id)
            return result
        if action == "strategy_review":
            result = self._run_strategy_review(input_data=input_data, user_id=user_id)
            return result
        if action == "force_approve_draft":
            result = self._run_force_approve(
                input_data=input_data,
                user_id=user_id,
                project_id=project_id,
                campaign_id=campaign_id,
            )
            return result
        if action == "run_step":
            return await self._run_step(
                input_data=input_data,
                stats=stats,
                user_id=user_id,
                project_id=project_id,
                campaign_id=campaign_id,
            )
        if action == "run_next_for_draft":
            return await self._run_next_for_draft(
                input_data=input_data,
                user_id=user_id,
                project_id=project_id,
                campaign_id=campaign_id,
            )
        if action == "auto_orchestrate":
            return await self._run_full_cycle(input_data, stats, user_id, project_id, campaign_id)
        self.logger.warning(f"Unknown action: {action}, returning stats")
        return AgentOutput(status="success", message="Stats retrieved", data={"stats": self._format_stats(stats)})

    async def _run_full_cycle(
        self, input_data: AgentInput, stats: dict, user_id: str, project_id: str, campaign_id: str
    ) -> AgentOutput:
        """Run full pipeline cycle via kernel dispatch (Scout -> Strategist -> Writer batch -> Critic batch -> ... -> Publisher)."""
        from backend.core.kernel import kernel

        base_params = {"project_id": project_id, "user_id": user_id, "campaign_id": campaign_id, **input_data.params}

        # Budget guard: block paid work (Scout/Strategist/Writer) if project over monthly limit
        try:
            spend = memory.get_monthly_spend(project_id)
            limit = settings.DEFAULT_PROJECT_LIMIT
            if spend >= limit:
                self.logger.warning(f"Budget exceeded for project {project_id}: ${spend:.2f} >= ${limit:.2f}")
                return AgentOutput(
                    status="error",
                    message="Budget exceeded. Monthly spend limit reached.",
                    data={"monthly_spend": spend, "project_limit": limit},
                )
        except Exception as e:
            self.logger.error(f"Budget check failed for project {project_id}: {e}")
            return AgentOutput(status="error", message="Failed to check project budget.")

        # Phase 1: Scout if no anchors
        if stats["anchors"] == 0:
            self.logger.info("No Anchors found. Deploying SCOUT...")
            res = await self._dispatch(kernel, "scout_anchors", base_params)
            if res.status == "error":
                return AgentOutput(status="error", message=f"Scout Failed: {res.message}")

        # Phase 2: Strategist if no keywords or no drafts (intent-cluster: Strategist creates page_drafts)
        if stats["anchors"] > 0 and (stats["kws_total"] == 0 or stats.get("drafts_total", 0) == 0):
            self.logger.info("No keywords/drafts. Deploying STRATEGIST...")
            res = await self._dispatch(kernel, "strategist_run", base_params)
            if res.status == "error":
                return AgentOutput(status="error", message=f"Strategist Failed: {res.message}")

        # Phase 3: Production line (batch each agent via kernel; Writer uses campaign batch_size)
        campaign = memory.get_campaign(campaign_id, user_id)
        pseo_settings = self._get_pseo_settings(campaign) if campaign else {}
        writer_batch_size = max(1, min(50, int(pseo_settings.get("batch_size", 5))))
        # So enhance_utility uses the project's lead gen campaign (form/call templates and webhook campaign_id)
        lead_gen_campaign_id = (campaign.get("config") or {}).get("lead_gen_campaign_id") if campaign else None
        if not lead_gen_campaign_id:
            lead_gen_campaigns = memory.get_campaigns_by_project(user_id, project_id, module="lead_gen")
            if lead_gen_campaigns:
                lead_gen_campaign_id = lead_gen_campaigns[0].get("id")
        if lead_gen_campaign_id:
            base_params["lead_gen_campaign_id"] = lead_gen_campaign_id

        for task_name, label in [
            ("write_pages", "WRITER"),
            ("critic_review", "CRITIC"),
            ("librarian_link", "LIBRARIAN"),
            ("enhance_media", "MEDIA"),
            ("enhance_utility", "UTILITY"),
        ]:
            self.logger.info(f"Checking {label} queue...")
            max_batch = writer_batch_size if task_name == "write_pages" else 5
            await self._run_batch(kernel, task_name, base_params, max_batch=max_batch)

        # Phase 4: Publisher (single run)
        self.logger.info("Checking PUBLISHER queue...")
        pub_res = await self._dispatch(kernel, "publish", {**base_params, "limit": 2})

        return AgentOutput(
            status="success",
            message="Manager Cycle Completed.",
            data={"pipeline_status": "Active", "last_publisher_msg": pub_res.message, "stats": self._format_stats(stats)},
        )

    async def _debug_run(
        self,
        input_data: AgentInput,
        stats: Dict[str, Any],
        user_id: str,
        project_id: str,
        campaign_id: str,
    ) -> AgentOutput:
        """Run a single end-to-end pass across the pipeline for debugging."""
        from backend.core.kernel import kernel

        base_params = {
            "project_id": project_id,
            "user_id": user_id,
            "campaign_id": campaign_id,
            **input_data.params,
        }
        # Force a safe batch size for this invocation only
        base_params.setdefault("batch_size", 1)

        logs = []

        async def _log_dispatch(task_name: str, label: str) -> None:
            task_input = AgentInput(task=task_name, user_id=user_id, params=base_params)
            try:
                res = await asyncio.wait_for(kernel.dispatch(task_input), timeout=300)
                logs.append(
                    {
                        "stage": label,
                        "task": task_name,
                        "status": res.status,
                        "message": res.message,
                    }
                )
            except asyncio.TimeoutError:
                logs.append(
                    {
                        "stage": label,
                        "task": task_name,
                        "status": "error",
                        "message": "Task timed out",
                    }
                )
            except Exception as e:
                logs.append(
                    {
                        "stage": label,
                        "task": task_name,
                        "status": "error",
                        "message": str(e),
                    }
                )

        # Run each major stage once to verify the chain.
        await _log_dispatch("scout_anchors", "Scout")
        await _log_dispatch("strategist_run", "Strategist")
        await _log_dispatch("write_pages", "Writer")
        await _log_dispatch("critic_review", "Critic")
        await _log_dispatch("librarian_link", "Librarian")
        await _log_dispatch("enhance_media", "Media")
        await _log_dispatch("enhance_utility", "Utility")
        await _log_dispatch("publish", "Publisher")

        return AgentOutput(
            status="success",
            message="Debug run executed.",
            data={
                "logs": logs,
                "stats": self._format_stats(stats),
            },
        )

    async def _dispatch(self, kernel, task_name: str, params: dict) -> AgentOutput:
        task_input = AgentInput(task=task_name, user_id=params["user_id"], params=params)
        return await asyncio.wait_for(kernel.dispatch(task_input), timeout=300)

    # Step names that run_step can dispatch (single-agent run)
    RUN_STEP_TASKS = [
        "scout_anchors",
        "strategist_run",
        "write_pages",
        "critic_review",
        "librarian_link",
        "enhance_media",
        "enhance_utility",
        "publish",
    ]

    # Draft status -> next pipeline step (for run_next_for_draft / phase-based UI)
    # Note: "rejected" sends the draft back to Writer so the same entity can be rewritten.
    DRAFT_STATUS_TO_NEXT_STEP = {
        "pending_writer": "write_pages",
        "draft": "critic_review",
        "rejected": "write_pages",
        "validated": "librarian_link",
        "ready_for_media": "enhance_media",
        "ready_for_utility": "enhance_utility",
        "utility_validation_failed": "enhance_utility",
        "ready_to_publish": "publish",
    }

    async def _run_step(
        self,
        input_data: AgentInput,
        stats: Dict[str, Any],
        user_id: str,
        project_id: str,
        campaign_id: str,
    ) -> AgentOutput:
        """
        Run a single pipeline step (one agent). Returns result and next_step for UI.
        Params: step or agent_key (e.g. scout_anchors, write_pages). Optional: auto_continue (ignored; frontend handles).
        """
        from backend.core.kernel import kernel

        step = input_data.params.get("step") or input_data.params.get("agent_key")
        if not step or step not in self.RUN_STEP_TASKS:
            return AgentOutput(
                status="error",
                message=f"run_step requires 'step' or 'agent_key' one of: {', '.join(self.RUN_STEP_TASKS)}",
            )
        base_params = {
            "project_id": project_id,
            "user_id": user_id,
            "campaign_id": campaign_id,
            **input_data.params,
        }
        if step == "enhance_utility":
            campaign = memory.get_campaign(campaign_id, user_id)
            lg_cid = (campaign.get("config") or {}).get("lead_gen_campaign_id") if campaign else None
            if not lg_cid:
                lead_gen_campaigns = memory.get_campaigns_by_project(user_id, project_id, module="lead_gen")
                if lead_gen_campaigns:
                    lg_cid = lead_gen_campaigns[0].get("id")
            if lg_cid:
                base_params["lead_gen_campaign_id"] = lg_cid
        try:
            result = await self._dispatch(kernel, step, base_params)
        except asyncio.TimeoutError:
            return AgentOutput(
                status="error",
                message=f"Step '{step}' timed out.",
                data={"step": step, "next_step": self._get_recommended_next_step(stats)},
            )
        except Exception as e:
            self.logger.error(f"run_step {step} failed: {e}", exc_info=True)
            return AgentOutput(
                status="error",
                message=f"Step failed: {str(e)}",
                data={"step": step, "next_step": self._get_recommended_next_step(stats)},
            )
        # Refresh stats after step for accurate next_step
        all_anchors = memory.get_entities(tenant_id=user_id, entity_type="anchor_location", project_id=project_id)
        all_kws = memory.get_entities(tenant_id=user_id, entity_type="seo_keyword", project_id=project_id)
        all_drafts = memory.get_entities(tenant_id=user_id, entity_type="page_draft", project_id=project_id)
        anchors = [a for a in all_anchors if a.get("metadata", {}).get("campaign_id") == campaign_id]
        kws = [k for k in all_kws if k.get("metadata", {}).get("campaign_id") == campaign_id]
        drafts = [d for d in all_drafts if d.get("metadata", {}).get("campaign_id") == campaign_id]
        drafts_pending_writer = len([d for d in drafts if d.get("metadata", {}).get("status") == "pending_writer"])
        stats_after = {
            "anchors": len(anchors),
            "kws_total": len(kws),
            "kws_pending": len([k for k in kws if k.get("metadata", {}).get("status") == "pending"]),
            "drafts_pending_writer": drafts_pending_writer,
            "drafts_total": len(drafts),
            "1_unreviewed": len([d for d in drafts if d.get("metadata", {}).get("status") in ("draft", "rejected")]),
            "2_validated": len([d for d in drafts if d.get("metadata", {}).get("status") == "validated"]),
            "3_linked": len([d for d in drafts if d.get("metadata", {}).get("status") == "ready_for_media"]),
            "4_imaged": len([d for d in drafts if d.get("metadata", {}).get("status") == "ready_for_utility"]),
            "5_ready": len([d for d in drafts if d.get("metadata", {}).get("status") == "ready_to_publish"]),
            "6_live": len([d for d in drafts if d.get("metadata", {}).get("status") in ("published", "live")]),
        }
        next_step = self._get_recommended_next_step(stats_after)
        return AgentOutput(
            status=result.status,
            message=result.message,
            data={
                "step": step,
                "result": result.data,
                "next_step": next_step,
                "stats": self._format_stats(stats_after),
            },
        )

    def _get_next_step_for_draft(self, draft: Dict[str, Any]) -> Optional[str]:
        """Return the pipeline step that should run next for this draft (phase-based control)."""
        status = (draft.get("metadata") or {}).get("status") or ""
        return self.DRAFT_STATUS_TO_NEXT_STEP.get(status)

    async def _run_next_for_draft(
        self,
        input_data: AgentInput,
        user_id: str,
        project_id: str,
        campaign_id: str,
    ) -> AgentOutput:
        """
        Run the next pipeline step for a specific draft (row-controlled). Dispatches the
        appropriate agent with draft_id so only this draft is processed.
        Params: draft_id (required).
        """
        from backend.core.kernel import kernel

        draft_id = input_data.params.get("draft_id")
        if not draft_id:
            return AgentOutput(status="error", message="run_next_for_draft requires draft_id.")

        draft = memory.get_entity(draft_id, user_id)
        if not draft:
            return AgentOutput(status="error", message="Draft not found or access denied.")
        if draft.get("entity_type") != "page_draft":
            return AgentOutput(status="error", message="Entity is not a page draft.")
        if (draft.get("metadata") or {}).get("campaign_id") != campaign_id:
            return AgentOutput(status="error", message="Draft does not belong to this campaign.")

        step = self._get_next_step_for_draft(draft)
        if not step:
            status = (draft.get("metadata") or {}).get("status", "")
            return AgentOutput(
                status="success",
                message=f"Draft has no next step (status: {status}).",
                data={"draft_id": draft_id, "step": None, "status": status},
            )

        base_params = {
            "project_id": project_id,
            "user_id": user_id,
            "campaign_id": campaign_id,
            "draft_id": draft_id,
            **input_data.params,
        }
        try:
            result = await self._dispatch(kernel, step, base_params)
        except asyncio.TimeoutError:
            return AgentOutput(
                status="error",
                message=f"Step '{step}' timed out.",
                data={"draft_id": draft_id, "step": step},
            )
        except Exception as e:
            self.logger.error(f"run_next_for_draft {step} failed: {e}", exc_info=True)
            return AgentOutput(
                status="error",
                message=f"Step failed: {str(e)}",
                data={"draft_id": draft_id, "step": step},
            )
        return AgentOutput(
            status=result.status,
            message=result.message,
            data={
                "draft_id": draft_id,
                "step": step,
                "result": result.data,
                "next_step": self._get_next_step_for_draft(memory.get_entity(draft_id, user_id) or {}),
            },
        )

    async def _run_batch(self, kernel, task_name: str, base_params: dict, max_batch: int = 5) -> None:
        """Run agent via kernel repeatedly until 'complete' or max_batch or error."""
        for _ in range(max_batch):
            task_input = AgentInput(task=task_name, user_id=base_params["user_id"], params=base_params)
            try:
                res = await asyncio.wait_for(kernel.dispatch(task_input), timeout=300)
            except asyncio.TimeoutError:
                self.logger.error(f"Task {task_name} timed out")
                break
            except Exception as e:
                self.logger.error(f"Task {task_name} error: {e}")
                break
            if res.status == "complete":
                break
            if res.status == "success":
                self.logger.info(f"  -> {task_name}: {res.message}")
            if res.status == "error":
                self.logger.error(f"{task_name} Error: {res.message}")
                break

    def _get_pulse_stats(self, stats: Dict[str, Any]) -> Dict[str, int]:
        """
        Map internal pipeline stats to Pulse funnel stages.

        Anchors Found      -> anchors
        Keywords Strategy  -> kws_total
        Drafts Written     -> all drafts across the pipeline
        Review Needed      -> 1_unreviewed (draft + rejected)
        Published          -> 6_live
        """
        total_drafts = (
            stats.get("1_unreviewed", 0)
            + stats.get("2_validated", 0)
            + stats.get("3_linked", 0)
            + stats.get("4_imaged", 0)
            + stats.get("5_ready", 0)
            + stats.get("6_live", 0)
        )
        return {
            "anchors": stats.get("anchors", 0),
            "keywords": stats.get("kws_total", 0),
            "drafts": total_drafts,
            "needs_review": stats.get("1_unreviewed", 0),
            "published": stats.get("6_live", 0),
        }

    def _get_pseo_settings(self, campaign: Dict[str, Any]) -> Dict[str, Any]:
        """
        Read per-campaign PSEO settings from campaign.config.
        """
        config = campaign.get("config") or {}
        settings = config.get("pseo_settings") or {}
        # Apply sane defaults if missing
        return {
            "batch_size": int(settings.get("batch_size", 5)),
            "speed_profile": settings.get("speed_profile", "balanced"),
        }

    def _update_pseo_settings(
        self,
        campaign_id: str,
        user_id: str,
        existing_config: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Update PSEO settings on the campaign config via memory helper.
        """
        from backend.core.memory import memory

        # Extract settings from params with basic validation
        raw_settings = params.get("settings") or {}
        batch_size = raw_settings.get("batch_size")
        speed_profile = raw_settings.get("speed_profile")

        new_settings: Dict[str, Any] = existing_config.get("pseo_settings", {}).copy()

        if batch_size is not None:
            try:
                batch_size_int = int(batch_size)
                # Clamp to a safe range
                batch_size_int = max(1, min(batch_size_int, 50))
                new_settings["batch_size"] = batch_size_int
            except (TypeError, ValueError):
                self.logger.warning(f"Invalid batch_size value: {batch_size}")

        if speed_profile:
            # Allow a small set of known profiles
            allowed_profiles = {"aggressive", "balanced", "human"}
            if speed_profile not in allowed_profiles:
                self.logger.warning(f"Invalid speed_profile value: {speed_profile}")
            else:
                new_settings["speed_profile"] = speed_profile

        merged_config = existing_config.copy()
        merged_config["pseo_settings"] = new_settings

        ok = memory.update_campaign_config(
            campaign_id=campaign_id,
            user_id=user_id,
            new_config=merged_config,
        )
        if not ok:
            return None

        return {"config": merged_config}

    def _run_intel_review(self, input_data: AgentInput, user_id: str) -> AgentOutput:
        """
        Bulk delete or exclude anchor_location entities for the Intel workbench.
        """
        from backend.core.memory import memory

        ids = input_data.params.get("ids") or []
        operation = input_data.params.get("operation") or "exclude"

        if not isinstance(ids, list) or not ids:
            return AgentOutput(
                status="error", message="No entity IDs provided for intel_review."
            )

        deleted = 0
        excluded = 0

        for entity_id in ids:
            try:
                if operation == "delete":
                    if memory.delete_entity(entity_id=entity_id, tenant_id=user_id):
                        deleted += 1
                else:
                    # Default to non-destructive exclusion flag
                    if memory.update_entity(
                        entity_id=entity_id, new_metadata={"excluded": True}, tenant_id=user_id
                    ):
                        excluded += 1
            except Exception as e:
                self.logger.error(f"intel_review failed for {entity_id}: {e}")

        return AgentOutput(
            status="success",
            message="Intel review applied.",
            data={"deleted": deleted, "excluded": excluded},
        )

    def _run_strategy_review(
        self,
        input_data: AgentInput,
        user_id: str,
    ) -> AgentOutput:
        """
        Bulk mark seo_keyword entities as approved or excluded.
        """
        from backend.core.memory import memory

        ids = input_data.params.get("ids") or []
        target_status = input_data.params.get("status") or "approved"

        if not isinstance(ids, list) or not ids:
            return AgentOutput(
                status="error", message="No keyword IDs provided for strategy_review."
            )

        updated = 0

        for entity_id in ids:
            try:
                if memory.update_entity(
                    entity_id=entity_id, new_metadata={"status": target_status}, tenant_id=user_id
                ):
                    updated += 1
            except Exception as e:
                self.logger.error(f"strategy_review failed for {entity_id}: {e}")

        return AgentOutput(
            status="success",
            message="Strategy review applied.",
            data={"updated": updated, "status": target_status},
        )

    def _run_force_approve(
        self,
        input_data: AgentInput,
        user_id: str,
        project_id: str,
        campaign_id: str,
    ) -> AgentOutput:
        """
        Force-approve a draft from the Quality workbench, optionally updating content.
        """
        from backend.core.memory import memory
        from backend.core.models import Entity

        draft_id = input_data.params.get("draft_id")
        updated_content = input_data.params.get("content")

        if not draft_id:
            return AgentOutput(
                status="error", message="draft_id is required for force_approve_draft."
            )

        draft = memory.get_entity(draft_id, user_id)
        if not draft:
            return AgentOutput(status="error", message="Draft not found or access denied.")

        meta = draft.get("metadata", {}) or {}
        if updated_content:
            # Support both 'content' and 'html_content' fields
            meta["content"] = updated_content
            meta["html_content"] = updated_content

        meta["status"] = "validated"
        meta.setdefault("qa_notes", "Force approved via dashboard.")
        draft["metadata"] = meta

        memory.save_entity(Entity(**draft), project_id=project_id)

        return AgentOutput(
            status="success",
            message="Draft force-approved.",
            data={
                "draft_id": draft_id,
                "campaign_id": campaign_id,
                "status": meta.get("status"),
            },
        )

    def _get_recommended_next_step(self, stats: dict) -> dict:
        if stats["5_ready"] > 0:
            return {"agent_key": "publish", "label": "Publisher", "description": "Publish ready content", "reason": f"{stats['5_ready']} pages ready to publish"}
        if stats["4_imaged"] > 0:
            return {"agent_key": "enhance_utility", "label": "Utility", "description": "Build lead magnets", "reason": f"{stats['4_imaged']} pages need tools"}
        if stats["3_linked"] > 0:
            return {"agent_key": "enhance_media", "label": "Media", "description": "Add images", "reason": f"{stats['3_linked']} pages need images"}
        if stats["2_validated"] > 0:
            return {"agent_key": "librarian_link", "label": "Librarian", "description": "Add internal links", "reason": f"{stats['2_validated']} pages need links"}
        if stats["1_unreviewed"] > 0:
            return {"agent_key": "critic_review", "label": "Critic", "description": "Quality check", "reason": f"{stats['1_unreviewed']} drafts need review"}
        drafts_pending_writer = stats.get("drafts_pending_writer", 0)
        kws_pending = stats.get("kws_pending", 0)
        if drafts_pending_writer > 0 or (kws_pending > 0 and stats.get("1_unreviewed", 0) < 2):
            reason = f"{drafts_pending_writer} drafts need writing" if drafts_pending_writer > 0 else f"{kws_pending} keywords need pages"
            return {"agent_key": "write_pages", "label": "Writer", "description": "Create content", "reason": reason}
        if stats["anchors"] == 0:
            return {"agent_key": "scout_anchors", "label": "Scout", "description": "Find locations", "reason": "No anchor locations found"}
        if stats.get("drafts_total", 0) == 0 and stats["anchors"] > 0:
            return {"agent_key": "strategist_run", "label": "Strategist", "description": "Create page drafts", "reason": "No page drafts yet; run Strategist"}
        if kws_pending > 0 and stats["anchors"] > 0:
            return {"agent_key": "strategist_run", "label": "Strategist", "description": "Generate keywords", "reason": f"Need more keywords ({stats['kws_total']}/{stats['anchors'] * 5})"}
        if stats["6_live"] > 20:
            return {"agent_key": "analytics_audit", "label": "Analytics", "description": "Analyze performance", "reason": f"{stats['6_live']} live pages ready for analysis"}
        return {"agent_key": None, "label": "Pipeline Balanced", "description": "All stages progressing well", "reason": "No immediate action needed"}

    def _format_stats(self, stats: dict) -> dict:
        return {
            "anchors": stats["anchors"],
            "kws_total": stats["kws_total"],
            "kws_pending": stats["kws_pending"],
            "drafts_pending_writer": stats.get("drafts_pending_writer", 0),
            "drafts_total": stats.get("drafts_total", 0),
            "Drafts": stats["1_unreviewed"] + stats["2_validated"] + stats["3_linked"] + stats["4_imaged"] + stats["5_ready"] + stats["6_live"],
            "1_unreviewed": stats["1_unreviewed"],
            "2_validated": stats["2_validated"],
            "3_linked": stats["3_linked"],
            "4_imaged": stats["4_imaged"],
            "5_ready": stats["5_ready"],
            "6_live": stats["6_live"],
        }
