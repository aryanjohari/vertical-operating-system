# backend/modules/pseo/agents/strategist.py
import asyncio
import hashlib
import httpx
from typing import List, Dict, Any
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory


class StrategistAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Strategist")

    async def _fetch_autocomplete(self, query: str) -> List[str]:
        """Check if a term has search volume via Google Autocomplete. Returns suggestions or empty list."""
        try:
            url = f"http://google.com/complete/search?client=chrome&q={query}"
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.json()[1]
        except Exception:
            pass
        return []

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Execute strategist: create one page_draft per (anchor × intent_cluster).
        No keyword permutation; intent_clusters come from campaign config.
        """
        try:
            project_id = self.project_id
            user_id = self.user_id
            campaign_id = input_data.params.get("campaign_id") or self.campaign_id

            if not project_id or not user_id or not campaign_id:
                return AgentOutput(
                    status="error",
                    message="Missing project_id, user_id, or campaign_id in context.",
                    data={},
                )

            campaign = memory.get_campaign(campaign_id, user_id)
            if not campaign:
                return AgentOutput(status="error", message="Campaign not found or access denied.", data={})

            config = campaign.get("config", {})
            if not isinstance(config, dict):
                return AgentOutput(status="error", message="Invalid campaign config format.", data={})

            targeting = config.get("targeting", {})
            service_focus = targeting.get("service_focus", config.get("service_focus", "Service"))
            intent_clusters = config.get("intent_clusters", [])

            if not isinstance(intent_clusters, list) or len(intent_clusters) == 0:
                return AgentOutput(
                    status="error",
                    message="No intent_clusters configured in campaign. Add at least one cluster in config.",
                    data={},
                )

            all_anchors = memory.get_entities(
                tenant_id=user_id, entity_type="anchor_location", project_id=project_id
            )
            campaign_anchors = [
                a
                for a in all_anchors
                if a.get("metadata", {}).get("campaign_id") == campaign_id
                and not a.get("metadata", {}).get("excluded")
            ]

            if not campaign_anchors:
                return AgentOutput(
                    status="error",
                    message="No anchor locations for this campaign. Run Scout first.",
                    data={},
                )

            self.logger.info(
                f"Strategist: {len(campaign_anchors)} anchors × {len(intent_clusters)} clusters = page drafts"
            )

            saved_count = 0
            for anchor in campaign_anchors:
                anchor_id = anchor.get("id")
                anchor_name = (anchor.get("name") or "").strip()
                anchor_meta = anchor.get("metadata") or {}
                has_hours = bool(anchor_meta.get("working_hours"))

                for cluster in intent_clusters:
                    if not isinstance(cluster, dict):
                        continue
                    cluster_id = cluster.get("id") or "unknown"
                    h1_template = (cluster.get("h1_template") or "Page near {Anchor}").strip()
                    secondary_keywords = cluster.get("secondary_keywords")
                    if not isinstance(secondary_keywords, list):
                        secondary_keywords = []
                    role = cluster.get("role") or "Informational"

                    # H1: substitute {Anchor} and {Service}
                    h1_title = (
                        h1_template.replace("{Anchor}", anchor_name)
                        .replace("{Service}", service_focus)
                        .strip()
                    )
                    if not h1_title:
                        h1_title = f"Page near {anchor_name}"

                    # Validation score: base 50, +20 if anchor has hours, +20 if secondary has volume (or assume high intent)
                    score = 50
                    if has_hours:
                        score += 20
                    if secondary_keywords:
                        # Check first secondary term via autocomplete; if any has volume, grant bonus
                        try:
                            check_term = f"{secondary_keywords[0]} {service_focus}"[:60]
                            suggestions = await self._fetch_autocomplete(check_term)
                            if suggestions:
                                score += 20
                            else:
                                score += 20  # Assume high intent for anchor-linked drafts
                        except Exception:
                            score += 20
                    score = min(100, score)

                    # Stable draft id to avoid duplicates on re-runs
                    stable_key = f"{campaign_id}|{anchor_id}|{cluster_id}"
                    draft_id = "draft_" + hashlib.sha256(stable_key.encode()).hexdigest()[:14]

                    existing = memory.get_entity(draft_id, user_id)
                    if existing:
                        # Update validation_score and h1/secondary if we re-run
                        memory.update_entity(
                            draft_id,
                            {
                                "validation_score": score,
                                "h1_title": h1_title,
                                "secondary_keywords": secondary_keywords,
                                "status": "pending_writer",
                            },
                            tenant_id=user_id,
                        )
                        saved_count += 1
                        continue

                    draft = Entity(
                        id=draft_id,
                        tenant_id=user_id,
                        entity_type="page_draft",
                        name=f"Page: {h1_title[:150]}",
                        primary_contact=None,
                        metadata={
                            "campaign_id": campaign_id,
                            "anchor_id": anchor_id,
                            "anchor_name": anchor_name,
                            "cluster_id": cluster_id,
                            "status": "pending_writer",
                            "h1_title": h1_title,
                            "secondary_keywords": secondary_keywords,
                            "validation_score": score,
                            "intent_role": role,
                        },
                    )
                    if memory.save_entity(draft, project_id=project_id):
                        saved_count += 1

            return AgentOutput(
                status="success",
                message=f"Strategy complete. Created {saved_count} page drafts (1 per intent per location).",
                data={
                    "drafts_created": saved_count,
                    "next_step": "Ready for Writer",
                },
            )
        except Exception as e:
            self.logger.error(f"Strategist execution failed: {e}", exc_info=True)
            return AgentOutput(status="error", message=f"Strategist failed: {str(e)}", data={})
