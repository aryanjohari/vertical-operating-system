# MASTER CONTEXT

## GOAL

## FILE: ARCHITECTURE_V4.md

# Apex Vertical Operating System — Architecture v4

**Version:** 4.0 (Campaign Architecture)  
**Audience:** Senior engineers, CTOs, system architects  
**Purpose:** Technical reference for the v4 codebase (branch `v4-campaign-architecture`).

---

## 1. System Overview

### Mission

Apex is a **Vertical Operating System** for service businesses that automates:

1. **Lead Capture** — 24/7 lead gen, instant bridge calls, lead scoring
2. **Client Communication** — Voice routing, transcription, call analysis
3. **SEO Dominance** — Programmatic SEO (pSEO) via location-keyword-content pipeline

### Core Philosophy: "The Invisible Bridge"

- **Customer** submits form → **System** calls **Client** → **Client** presses "1" → **Customer** connected
- **Customer** calls Maps listing → **System** forwards, records, transcribes, analyzes → **Client** gets structured lead
- **System** scrapes job boards → scores leads → triggers bridge calls for high-value leads

The client rarely needs to log in; value is routed to their phone.

### Tech Stack

| Layer               | Technology                                   | Purpose                                              |
| ------------------- | -------------------------------------------- | ---------------------------------------------------- |
| **Backend**         | Python 3.9+, FastAPI, Uvicorn                | REST API, agent orchestration                        |
| **Frontend**        | Next.js, TypeScript, Tailwind                | Dashboard, campaigns, entities                       |
| **Database**        | PostgreSQL / SQLite (DatabaseFactory)        | Users, projects, campaigns, entities, usage          |
| **Vector**          | ChromaDB + Google `text-embedding-004`       | RAG (brand brain, knowledge fragments)               |
| **Cache / context** | Redis (optional)                             | Short-lived agent context (TTL tickets)              |
| **AI**              | Google Gemini (LLM Gateway)                  | Content, analysis, embeddings                        |
| **Comms**           | Twilio                                       | Voice, SMS, bridge calls, recording                  |
| **Scraping**        | Playwright (maps_sync), Serper (search_sync) | Maps scout, competitor/fact search                   |
| **Concurrency**     | FastAPI BackgroundTasks                      | Heavy tasks (scout, strategist, sniper, sales, etc.) |

---

## 2. V4 Campaign Architecture

### Hierarchy

```
User (tenant_id)
  └── Project (project_id) — DNA: identity, brand_brain, modules
        └── Campaign (campaign_id) — module-specific config
              ├── pSEO: targeting, mining_requirements, assets, pseo_settings, cms_settings
              └── Lead Gen: sniper, outreach, bridge
```

- **Project** = business/client. Has `dna.generated.yaml` + `dna.custom.yaml` under `data/profiles/{project_id}/`.
- **Campaign** = execution unit. Stored in `campaigns` table (`id`, `project_id`, `name`, `module`, `status`, `config`, `stats`). Config is module-specific and merged with DNA when agents run.
- **Module** = `pseo` | `lead_gen`. Each campaign belongs to one module.

### Config Loading (ConfigLoader)

**Merge order:** System defaults → DNA (generated → custom) → Campaign config (when `campaign_id` provided).

- **`ConfigLoader.load(project_id, campaign_id=None)`**
  - Loads DNA; if `campaign_id` given, loads campaign from DB (and optional disk backup at `data/profiles/{project_id}/campaigns/{campaign_id}.yaml`), then merges campaign config into `modules.{module}`.
- **`ConfigLoader.load_dna(project_id)`** — DNA only.
- **`ConfigLoader.load_campaign_config(campaign_id, user_id=None)`** — Campaign config only (RLS when `user_id` provided).
- **`ConfigLoader.merge_config(dna, campaign_config)`** — Merges campaign into `modules[module]` or top-level `campaign` key.

### Campaign-Agent Coupling

- **pSEO:** `manager` and workers (`scout_anchors`, `strategist_run`, `write_pages`, `critic_review`, `librarian_link`, `enhance_media`, `enhance_utility`, `publish`, `analytics_audit`) require `campaign_id`. They use **campaign config** as source of truth for targeting, mining, etc.; **DNA** for identity/brand.
- **Lead Gen:** `lead_gen_manager` and workers (`sniper_agent`, `sales_agent`, `reactivator_agent`, `lead_scorer`, `utility`) require `campaign_id`. Config comes from merged DNA + campaign.
- **Onboarding** creates projects and campaigns; **system ops** (`health_check`, `cleanup`, `log_usage`) are system-level and do not use campaigns.

---

## 3. Request Flow and Concurrency

### Entry Points

- **`POST /api/run`** — Main agent entry. Accepts `AgentInput` (`task`, `user_id`, `params`). `user_id` is overridden from JWT.
- **Webhooks** — `POST /api/webhooks/...` (e.g. Google Ads, WordPress). Create leads and can trigger `sales_agent` (bridge).
- **Voice** — `POST /api/voice/...` (Twilio). Inbound, connect, status, recording-status, transcription.

### Opt-Out Async (Heavy vs Instant)

- **Heavy tasks:** Queued to `BackgroundTasks`, return immediately with `status: "processing"` and `context_id`. Client polls `GET /api/context/{context_id}` until `data.status` is `completed` or `failed`.
- **Instant actions:** Run synchronously; no ticket; full result in HTTP response.

**Heavy (async):**  
`sniper_agent`, `sales_agent`, `reactivator_agent`, `scout_anchors`, `strategist_run`; and when triggered via manager: `hunt_sniper`, `ignite_reactivation`, `instant_call`.

**Instant (sync):**  
`manager` with `action: "dashboard_stats"` or `"pulse_stats"` etc.; `lead_gen_manager` with `action: "dashboard_stats"`; `health_check`; `log_usage`; other fast ops.

### Context (Redis / In-Memory)

- **ContextManager** (`backend/core/context.py`): Creates TTL-bound **AgentContext** (project_id, user_id, data).
- **Storage:** Redis `context:{context_id}` with TTL (default 3600s), or in-memory dict if Redis unavailable.
- **Flow:** Heavy task → create context → enqueue → return `context_id` → worker updates context on completion → client polls.

---

## 4. Kernel and Agent Dispatch

### Kernel (`backend/core/kernel.py`)

1. **Resolve agent** from `task` via `_resolve_agent`: exact match, else prefix match (e.g. `onboarding_start` → `onboarding`).
2. **System agents** (`onboarding`, `health_check`, `cleanup`, `log_usage`): Skip DNA load. `log_usage` still needs `project_id` (from params) and project-ownership check.
3. **Regular agents:**
   - Resolve `project_id`: from `params.niche` / `params.project_id`, or `memory.get_user_project(user_id)`.
   - Validate `project_id` format (regex `^[a-zA-Z0-9_-]+$`) and **verify project ownership**.
   - Optional `campaign_id` from `params`.
   - **ConfigLoader.load(project_id, campaign_id)** → merged config.
   - Inject `config`, `project_id`, `user_id`, `campaign_id` into agent instance.
4. **Execute** `agent.run(packet)` → `AgentOutput`.

### Agent Registry (`backend/core/registry.py`)

**AgentRegistry.DIRECTORY** maps `task` → `(module_path, ClassName)`:

| Task                 | Module                                         | Class              |
| -------------------- | ---------------------------------------------- | ------------------ |
| `onboarding`         | `backend.modules.onboarding.genesis`           | `OnboardingAgent`  |
| `manager`            | `backend.modules.pseo.manager`                 | `ManagerAgent`     |
| `scout_anchors`      | `backend.modules.pseo.agents.scout`            | `ScoutAgent`       |
| `strategist_run`     | `backend.modules.pseo.agents.strategist`       | `StrategistAgent`  |
| `write_pages`        | `backend.modules.pseo.agents.writer`           | `WriterAgent`      |
| `critic_review`      | `backend.modules.pseo.agents.critic`           | `CriticAgent`      |
| `librarian_link`     | `backend.modules.pseo.agents.librarian`        | `LibrarianAgent`   |
| `enhance_media`      | `backend.modules.pseo.agents.media`            | `MediaAgent`       |
| `enhance_utility`    | `backend.modules.lead_gen.agents.utility`      | `UtilityAgent`     |
| `publish`            | `backend.modules.pseo.agents.publisher`        | `PublisherAgent`   |
| `analytics_audit`    | `backend.modules.pseo.agents.analytics`        | `AnalyticsAgent`   |
| `lead_gen_manager`   | `backend.modules.lead_gen.manager`             | `LeadGenManager`   |
| `sniper_agent`       | `backend.modules.lead_gen.agents.sniper`       | `SniperAgent`      |
| `sales_agent`        | `backend.modules.lead_gen.agents.sales`        | `SalesAgent`       |
| `reactivator_agent`  | `backend.modules.lead_gen.agents.reactivator`  | `ReactivatorAgent` |
| `lead_scorer`        | `backend.modules.lead_gen.agents.scorer`       | `LeadScorerAgent`  |
| `system_ops_manager` | `backend.modules.system_ops.manager`           | `SystemOpsManager` |
| `health_check`       | `backend.modules.system_ops.agents.sentinel`   | `SentinelAgent`    |
| `log_usage`          | `backend.modules.system_ops.agents.accountant` | `AccountantAgent`  |
| `cleanup`            | `backend.modules.system_ops.agents.janitor`    | `JanitorAgent`     |

**ModuleManifest.CATALOG** (frontend “app store”): `local_seo` (pSEO), `lead_gen`, with `agents` and `config_required` per module.

### BaseAgent (`backend/core/agent_base.py`)

- **Injected by Kernel:** `config`, `project_id`, `user_id`, `campaign_id`.
- **`run(input_data)`** wraps `_execute(input_data)`, handles logging and error → `AgentOutput`.
- **`_execute`** is abstract; each agent implements it.

### Universal Packet Types (`backend/core/models.py`)

- **AgentInput:** `task`, `user_id`, `params`, `request_id`.
- **AgentOutput:** `status`, `data`, `message`, `timestamp`.
- **Entity:** `id`, `tenant_id`, `entity_type`, `name`, `primary_contact`, `metadata`, `created_at`.

---

## 5. Database and Memory

### DatabaseFactory (`backend/core/db.py`)

- **Detection:** `DATABASE_URL` with `postgres://` or `postgresql://` → PostgreSQL; else SQLite.
- **Abstractions:** placeholders (`%s` vs `?`), `INSERT OR REPLACE` vs `ON CONFLICT`, `date_trunc` vs `date('now', 'start of month')`, row factories.
- **Usage:** `get_db_factory(db_path)` → factory; `get_cursor()`, `get_connection()`, etc.

### Tables (MemoryManager `_init_database`)

- **users** — `user_id`, `password_hash`, `salt`.
- **projects** — `project_id`, `user_id`, `niche`, `dna_path`, `created_at`.
- **entities** — `id`, `tenant_id`, `project_id`, `entity_type`, `name`, `primary_contact`, `metadata` (JSON/JSONB), `created_at`. Indexes: `tenant_id`, `project_id`.
- **campaigns** — `id` (e.g. `cmp_xxxxxxxxxx`), `project_id`, `name`, `module`, `status`, `config`, `stats`, `created_at`, `updated_at`. Indexes: `project_id`, `module`, `status`.
- **client_secrets** — `user_id`, `wp_url`, `wp_user`, `wp_auth_hash` (WordPress).
- **usage_ledger** — `id`, `project_id`, `resource_type`, `quantity`, `cost_usd`, `timestamp`. Index: `(project_id, timestamp)`.

### Entity Types and Campaign Scoping

Entities are optionally scoped by `metadata.campaign_id`:

- **`anchor_location`** — Scout output (Maps places). Metadata: address, maps URL, `campaign_id`, etc.
- **`knowledge_fragment`** — Scout/search intel (competitor/fact snippets). Metadata: `fragment_type`, `url`, `campaign_id`, etc.
- **`seo_keyword`** — Strategist output. Metadata: `cluster_data`, `anchor_reference`, `status` (`pending`|`approved`|`excluded`), `campaign_id`.
- **`page_draft`** — Writer → … → Publisher. Metadata: `keyword`, `anchor_used`, `content`/`html_content`, `status` (see below), `campaign_id`, `slug`, `live_url`, etc.
- **`lead`** — Lead-gen flows. Metadata: `source`, `status`, `score`, `campaign_id`, `call_sid`, `call_transcription`, `call_analysis`, etc.

### Page Draft Status Flow (pSEO Pipeline)

```
draft ──Critic PASS──► validated ──Librarian──► ready_for_media ──Media──► ready_for_utility ──Utility──► ready_to_publish ──Publisher──► published
         └─ FAIL ──► rejected
```

- **Manager stats:** `1_unreviewed` = draft + rejected; `2_validated` … `6_live` map to validated → linked → imaged → ready → live.

### MemoryManager RAG (ChromaDB)

- **Collection:** `apex_context`.
- **Embeddings:** `GoogleEmbeddingFunction` via LLM Gateway (`text-embedding-004`).
- **`save_context`** / **`query_context`** filter by `tenant_id`, optional `project_id`, optional `campaign_id`.
- Used for brand brain, knowledge nuggets, and Writer RAG over `knowledge_fragment`-style content.

### Campaign CRUD (MemoryManager)

- **`create_campaign`**, **`get_campaign`**, **`get_campaigns_by_project`** (optional `module` filter).
- **`update_campaign_status`**, **`update_campaign_stats`**, **`update_campaign_config`**.
- All enforce project ownership (via `get_campaign` or explicit checks).

---

## 6. Services

### LLM Gateway (`backend/core/services/llm_gateway.py`)

- Single entry for Gemini calls: `generate_content`, `generate_embeddings`.
- Used by Writer, Critic, Strategist, onboarding, transcription analysis, etc.

### Maps Sync (`backend/core/services/maps_sync.py`)

- **`run_scout_sync(queries, allow_kws, block_kws)`** — Playwright, Google Maps search; infinite scroll; extract place name, address, link, phone. Returns list of dicts.
- Used by **ScoutAgent** to create `anchor_location` entities (and optionally trigger intel mining).

### Search Sync (`backend/core/services/search_sync.py`)

- **`run_search_sync(query_objects)`** — Serper API. `query_objects`: `[{ "query": str, "type": "competitor"|"fact" }]`. Returns `{ query, title, link, snippet, type }`.
- Used by Scout for competitor/fact mining → **`knowledge_fragment`** entities.

### Transcription (`backend/core/services/transcription.py`)

- Transcribes Twilio recordings (e.g. via Gemini).
- Used by voice flow and **LeadGenManager** `transcribe_call` action.

### Universal Scraper (`backend/core/services/universal.py`)

- General website scrape.
- Used by **OnboardingAgent** for optional site scrape when compiling DNA.

---

## 7. pSEO Module (Apex Growth)

### Manager (`manager`)

- **Requires:** `project_id`, `user_id`, `campaign_id`; `modules.local_seo.enabled` and campaign `module === "pseo"`.
- **Actions:**
  - `dashboard_stats` — Pipeline counts (anchors, keywords, drafts by status), `next_step` recommendation.
  - `pulse_stats` — Funnel-style stats (anchors, keywords, drafts, needs_review, published).
  - `get_settings` / `update_settings` — Per-campaign `pseo_settings` (e.g. `batch_size`, `speed_profile`).
  - `debug_run` — Single pass Scout → Strategist → Writer → Critic → Librarian → Media → Utility → Publisher.
  - `intel_review` — Bulk exclude/delete `anchor_location` entities (Intel workbench).
  - `strategy_review` — Bulk set `seo_keyword` `status` (e.g. approved/excluded).
  - `force_approve_draft` — Set `page_draft` to `validated`, optionally update content.
  - `auto_orchestrate` — Full cycle: Scout (if no anchors) → Strategist (if no keywords) → batch Writer, Critic, Librarian, Media, Utility → Publisher.

### Pipeline (Worker Agents)

- **ScoutAgent** — Reads campaign `targeting`, `mining_requirements`. Runs **maps_sync** (anchors) and **search_sync** (competitor/fact). Saves `anchor_location` and `knowledge_fragment` with `campaign_id`.
- **StrategistAgent** — Uses `anchor_location` and campaign `targeting`; generates `seo_keyword` entities with `anchor_reference`, `cluster_data`, `status: "pending"`.
- **WriterAgent** — Picks `pending` keyword; optional `anchor_reference` → anchor details (uses `memory.get_entity`; **see Known Gap**); RAG from ChromaDB + `knowledge_fragment`; produces HTML with `{{form_capture}}`, `{{image_main}}`, etc. Saves `page_draft` with `status: "draft"`.
- **CriticAgent** — Reviews `draft`; PASS (score ≥ 7) → `validated`, FAIL → `rejected`.
- **LibrarianAgent** — Internal links + optional “References” from `knowledge_fragment`; `validated` → `ready_for_media`.
- **MediaAgent** — Unsplash (or fallback) image; `ready_for_media` → `ready_for_utility`.
- **UtilityAgent** — JSON-LD schema; `{{form_capture}}` injection if lead_gen enabled; `ready_for_utility` / `ready_for_media` → `ready_to_publish`.
- **PublisherAgent** — WordPress REST API; `ready_to_publish` → `published`; updates `live_url`, etc. Reads CMS config from campaign `cms_settings` or DNA `local_seo.publisher_settings`.
- **AnalyticsAgent** — Consumes `page_draft` with `status` published/live for analytics/audit.

### Campaign Config (pSEO)

- **Templates:** `backend/core/templates/pseo_default.yaml` (targeting, mining_requirements, assets).
- **Targeting:** `service_focus`, `geo_targets.cities`, `geo_targets.suburbs`.
- **Mining:** `regulatory`, `competitor`, `geo_context` (queries, extraction_goals, target_anchors).
- **Assets:** e.g. `comparison_table`, `regulatory_alert`, `lead_magnet`.
- **pseo_settings:** `batch_size`, `speed_profile`.
- **cms_settings:** WordPress URL, username (password in `client_secrets`).

---

## 8. Lead Gen Module (Apex Connect)

### LeadGenManager (`lead_gen_manager`)

- **Requires:** `project_id`, `user_id`, `campaign_id`; campaign `module === "lead_gen"`; `modules.lead_gen.enabled`.
- **Actions:**
  - `hunt_sniper` — Dispatch **SniperAgent**; then batch **LeadScorerAgent** for new unscored leads.
  - `ignite_reactivation` — Dispatch **ReactivatorAgent** (SMS blast).
  - `instant_call` — Dispatch **SalesAgent** with `action: "instant_call"`, `lead_id`.
  - `transcribe_call` — Fetch recording, run transcription service, Gemini analysis, update lead `metadata`.
  - `dashboard_stats` (default) — Counts, sources, priorities, conversion, pipeline value, recent leads (all campaign-scoped).

### Workers

- **SniperAgent** — Scrapes job boards (e.g. TradeMe, Facebook Groups); creates `lead` entities with `campaign_id`; dedupes.
- **SalesAgent** — Bridge calls (Twilio): call boss → whisper → press 1 → connect customer; `instant_call`, `notify_sms`. Uses DNA/campaign bridge config (destination phone, whisper, SMS).
- **ReactivatorAgent** — SMS to old leads (e.g. status won/completed, last contact > threshold).
- **LeadScorerAgent** — Scores leads via LLM; updates `metadata.score`.
- **UtilityAgent** — Shared with pSEO; adds schema and form injection for `ready_for_utility` / `ready_for_media` drafts.

### Campaign Config (Lead Gen)

- **Templates:** `backend/core/templates/lead_gen_default.yaml`.
- **Sniper:** `platforms`, `search_terms`, `geo_filter`, `exclusions`.
- **Outreach:** `mode`, `response_templates`.
- **Bridge:** `destination_phone`, `whisper_text`, `sms_alert`.

---

## 9. Onboarding Module

### OnboardingAgent (`onboarding`)

- **System agent:** No DNA load.
- **Actions:**
  - **`compile_profile`** — Identity + modules from params; optional site scrape (UniversalScraper); LLM compiles DNA from **`profile_template.yaml`**; writes `dna.generated.yaml`; creates project via `memory.register_project`; saves RAG context.
  - **`create_campaign`** — Interactive campaign creation (interview); creates campaign via `memory.create_campaign`; can write campaign YAML under `data/profiles/{project_id}/campaigns/`.

### Templates

- **`backend/core/templates/profile_template.yaml`** — DNA shape: `identity`, `brand_brain`, `modules` (local_seo, lead_gen, admin).
- **`pseo_default.yaml`**, **`lead_gen_default.yaml`** — Campaign config defaults.

---

## 10. System Ops Module

- **SystemOpsManager** — Orchestrator; e.g. `run_diagnostics` → **SentinelAgent**.
- **SentinelAgent** (`health_check`) — Checks DB, Twilio, Gemini, disk, etc.
- **AccountantAgent** (`log_usage`) — Writes `usage_ledger`; uses `project_id` from params; project ownership verified.
- **JanitorAgent** (`cleanup`) — Log/download cleanup.

---

## 11. Frontend (High Level)

- **Auth:** Login/register; JWT via `api` axios instance (`Authorization: Bearer`).
- **Projects:** List, create; create triggers onboarding.
- **Project dashboard** (`/projects/[id]`): **CampaignSelector**, **CreateCampaignModal**; **Pipeline** (pSEO) or **LeadGenDashboard** + **LeadGenActions** + **LeadsList** (lead_gen) depending on selected campaign `module`.
- **Pipeline:** Stages Scout → … → Publisher → Analytics; **AgentButton** per stage; **auto_orchestrate** calls `manager` with `action: "auto_orchestrate"`.
- **pSEO sub-pages:** e.g. `/projects/[id]/pseo/intel`, `strategy`, `quality` (ScoutRunner, StrategistRunner, Intel/Strategy/Quality workbenches).
- **Entities:** `/projects/[id]/entities` — **EntityManager** (CRUD).
- **Settings:** `/projects/[id]/settings` — **DNAEditor**, WordPress, etc.
- **Onboarding:** **ModuleSelector** (pSEO vs lead_gen) → **CampaignCreator** (interview) or **URLInput** → **OnboardingFlow**.

### API Usage

- **`POST /api/run`** with `task`, `params` (incl. `project_id`, `campaign_id` for campaign-scoped tasks).
- **`GET /api/context/{context_id}`** for polling async tasks.
- **`HEAVY_TASKS`** / **`isHeavyTask`**, **`pollContextUntilComplete`** in `frontend/lib/api.ts`.

---

## 12. Webhooks and Voice

- **Webhooks** (`/api/webhooks/...`): Normalize lead payload, validate `project_id`, get `user_id` from project owner; create **lead** entity; optionally trigger **SalesAgent** (bridge). Support background execution via **BackgroundTasks**.
- **Voice** (`/api/voice/...`): Twilio inbound, connect, status, recording-status, transcription. Forward to boss, record, transcribe, analyze, update lead.

---

## 13. Security and Multi-Tenancy

- **RLS:** All entity and campaign access filtered by `tenant_id` (user_id) and project ownership.
- **Project ownership:** `memory.verify_project_ownership(user_id, project_id)` before config load and agent dispatch.
- **`project_id`** format enforced (alphanumeric, underscore, hyphen).
- **Secrets:** WordPress password stored encrypted (`client_secrets.wp_auth_hash`).
- **JWT:** `user_id` from token; never trusted from client.

---

## 14. Known Gaps and Fixes

- **`memory.get_entity`** — Used in **WriterAgent** (anchor by `anchor_reference`) and **ManagerAgent** (`force_approve_draft`). Not implemented in **MemoryManager**. Implement as `get_entity(entity_id, tenant_id) -> Optional[dict]` (e.g. `SELECT * FROM entities WHERE id = ? AND tenant_id = ?`) and use it in both places.
- **Scheduler:** Main lifespan uses APScheduler for periodic `health_check` and daily `cleanup`. Health interval in code is 1440 minutes (once per day); typically intended 5 minutes — verify trigger config.

---

## 15. File and Directory Reference

| Path                                      | Purpose                                                                                                  |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `backend/main.py`                         | FastAPI app, `/api/run`, context, auth, entities, projects, campaigns, leads, settings, DNA, usage, logs |
| `backend/core/kernel.py`                  | Dispatch, resolve agent, load config, inject context                                                     |
| `backend/core/registry.py`                | AgentRegistry.DIRECTORY, ModuleManifest.CATALOG                                                          |
| `backend/core/config.py`                  | ConfigLoader, Settings (e.g. SERPER_API_KEY)                                                             |
| `backend/core/memory.py`                  | MemoryManager, DB init, campaigns, entities, RAG, usage                                                  |
| `backend/core/context.py`                 | ContextManager, Redis/in-memory context                                                                  |
| `backend/core/agent_base.py`              | BaseAgent, run, \_execute                                                                                |
| `backend/core/models.py`                  | AgentInput, AgentOutput, Entity                                                                          |
| `backend/core/db.py`                      | DatabaseFactory, get_db_factory                                                                          |
| `backend/core/templates/`                 | profile_template, pseo_default, lead_gen_default                                                         |
| `backend/core/services/`                  | llm_gateway, maps_sync, search_sync, transcription, universal                                            |
| `backend/modules/pseo/manager.py`         | ManagerAgent                                                                                             |
| `backend/modules/pseo/agents/`            | scout, strategist, writer, critic, librarian, media, publisher, analytics                                |
| `backend/modules/lead_gen/manager.py`     | LeadGenManager                                                                                           |
| `backend/modules/lead_gen/agents/`        | sniper, sales, reactivator, scorer, utility                                                              |
| `backend/modules/onboarding/genesis.py`   | OnboardingAgent                                                                                          |
| `backend/modules/system_ops/`             | manager, sentinel, accountant, janitor                                                                   |
| `backend/routers/`                        | voice, webhooks                                                                                          |
| `data/profiles/{project_id}/`             | dna.generated.yaml, dna.custom.yaml, campaigns/\*.yaml                                                   |
| `frontend/app/(dashboard)/projects/[id]/` | Project dashboard, pseo/\*, entities, settings                                                           |
| `frontend/components/`                    | campaigns/_, leadgen/_, pseo/_, project/_, onboarding/_, entities/_, settings/\*                         |

---

**Document Version:** 4.0  
**Last Updated:** January 2026  
**Branch:** v4-campaign-architecture

## FILE: backend/main.py

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
from typing import Optional, Dict, Any, List
from backend.core.models import AgentInput, AgentOutput, Entity
from backend.core.kernel import kernel
from backend.core.memory import memory
from backend.core.schemas import TASK_SCHEMA_MAP
from backend.core.logger import setup_logging
from backend.core.auth import (
get_current_user,
create_access_token,
verify_user_credentials
)
from backend.routers.voice import voice_router
from backend.routers.webhooks import webhook_router
from backend.modules.system_ops.middleware import security_middleware
from backend.core.context import context_manager
from contextlib import asynccontextmanager
import logging
import uvicorn
import os
import re
import traceback
import json
import yaml
from datetime import datetime
from backend.core.db import get_db_factory

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(**file**)))

setup_logging()
logger = logging.getLogger("Apex.Main")

scheduler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
"""Lifespan context manager for startup and shutdown events."""
global scheduler

    logger.info("🚀 Starting Apex Sovereign OS...")

    # Ensure usage_ledger table exists before dashboard queries
    try:
        memory.create_usage_table_if_not_exists()
        logger.info("✅ Usage ledger table initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize usage ledger table: {e}", exc_info=True)
        # Don't fail startup, but log the error

    # Initialize scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        from apscheduler.triggers.cron import CronTrigger

        scheduler = AsyncIOScheduler()

        # Schedule health check every 5 minutes
        async def run_health_check():
            try:
                logger.debug("🔍 Running scheduled health check...")
                from backend.core.models import AgentInput
                # Call health_check directly (system agent, no project needed)
                result = await kernel.dispatch(
                    AgentInput(
                        task="health_check",
                        user_id="system",
                        params={}
                    )
                )
                if result.status == "error":
                    logger.warning(f"Health check failed: {result.message}")
                else:
                    logger.debug(f"Health check completed: {result.data.get('status', 'unknown')}")
            except Exception as e:
                logger.error(f"Error in scheduled health check: {e}", exc_info=True)

        # Schedule cleanup every 24 hours at 3 AM
        async def run_cleanup():
            try:
                logger.info("🧹 Running scheduled cleanup...")
                from backend.core.models import AgentInput
                result = await kernel.dispatch(
                    AgentInput(
                        task="cleanup",
                        user_id="system",
                        params={}
                    )
                )
                if result.status == "error":
                    logger.warning(f"Cleanup failed: {result.message}")
                else:
                    logger.info(f"Cleanup completed: {result.message}")
            except Exception as e:
                logger.error(f"Error in scheduled cleanup: {e}", exc_info=True)

        # Add jobs
        scheduler.add_job(
            run_health_check,
            trigger=IntervalTrigger(minutes=1440),
            id="health_check",
            replace_existing=True
        )

        scheduler.add_job(
            run_cleanup,
            trigger=CronTrigger(hour=3, minute=0),  # 3 AM daily
            id="cleanup",
            replace_existing=True
        )

        scheduler.start()
        logger.info("✅ Scheduler started (health check: every 5min, cleanup: daily at 3 AM)")
    except ImportError:
        logger.warning("⚠️ APScheduler not available, scheduled jobs disabled")
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}", exc_info=True)

    yield

    # Shutdown
    logger.info("🛑 Shutting down Apex Sovereign OS...")
    if scheduler:
        try:
            scheduler.shutdown()
            logger.info("✅ Scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}", exc_info=True)

# Initialize the App

app = FastAPI(
title="Apex Sovereign OS",
version="1.0",
description="The Vertical Operating System for Revenue & Automation",
lifespan=lifespan
)

# CORS Configuration (secure defaults, configurable via env)

ALLOWED_ORIGINS = os.getenv(
"APEX_CORS_ORIGINS",
"http://localhost:3000,http://localhost:3001,http://localhost:5500" # Default: Next.js dev ports
).split(",")

app.add_middleware(
CORSMiddleware,
allow_origins=["*"], # Whitelist specific origins
allow_credentials=True,
allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
allow_headers=["Content-Type", "Authorization"],
)

# Add security middleware

app.middleware("http")(security_middleware)

@app.get("/")
def health_check():
"""Ping this to check if the OS is alive."""
return {
"status": "online",
"system": "Apex Kernel",
"version": "1.0",
"loaded_agents": list(kernel.agents.keys())
}

@app.get("/health")
def health_check_endpoint():
"""Ping this to check if the OS is alive."""
return {
"status": "online",
"system": "Apex Kernel",
"version": "1.0",
"loaded_agents": list(kernel.agents.keys())
}

@app.get("/api/health")
def api_health_check():
"""Enhanced health check endpoint with component status."""
health_status = {
"status": "online",
"system": "Apex Kernel",
"version": "1.0",
"loaded_agents": list(kernel.agents.keys()),
"redis_ok": False,
"database_ok": False,
"twilio_ok": False
}

    # Check Redis
    try:
        if context_manager.enabled and context_manager.redis_client:
            context_manager.redis_client.ping()
            health_status["redis_ok"] = True
    except Exception as e:
        logger.debug(f"Redis check failed: {e}")
        health_status["redis_ok"] = False

    # Check Database
    try:
        db_factory = get_db_factory(db_path=memory.db_path)
        with db_factory.get_cursor(commit=False) as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        health_status["database_ok"] = True
    except Exception as e:
        logger.debug(f"Database check failed: {e}")
        health_status["database_ok"] = False

    # Check Twilio (check if credentials are configured)
    try:
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        health_status["twilio_ok"] = bool(twilio_sid and twilio_token)
    except Exception as e:
        logger.debug(f"Twilio check failed: {e}")
        health_status["twilio_ok"] = False

    return health_status

@app.get("/api/logs")
async def get_logs(
lines: int = 50,
user_id: str = Depends(get_current_user)
):
"""Get the last N lines from the system log file."""
try:
log_file_path = os.path.join(BASE_DIR, "logs", "apex.log")

        if not os.path.exists(log_file_path):
            return {
                "logs": [],
                "total_lines": 0,
                "message": "Log file not found"
            }

        # Read last N lines from file
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        # Remove trailing newlines and return
        cleaned_lines = [line.rstrip('\n\r') for line in last_lines]

        return {
            "logs": cleaned_lines,
            "total_lines": len(cleaned_lines)
        }
    except Exception as e:
        logger.error(f"Error reading logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to read logs")

@app.get("/api/usage")
async def get_usage(
project_id: Optional[str] = None,
limit: int = 100,
user_id: str = Depends(get_current_user)
):
"""Get usage records from the usage_ledger table."""
try:
db_factory = get_db_factory(db_path=memory.db_path)
placeholder = db_factory.get_placeholder()

        # If project_id provided, verify ownership
        if project_id:
            if not memory.verify_project_ownership(user_id, project_id):
                raise HTTPException(status_code=403, detail="Project not found or access denied")

            # Query for specific project
            with db_factory.get_cursor(commit=False) as cursor:
                cursor.execute(f'''
                    SELECT id, project_id, resource_type, quantity, cost_usd, timestamp
                    FROM usage_ledger
                    WHERE project_id = {placeholder}
                    ORDER BY timestamp DESC
                    LIMIT {placeholder}
                ''', (project_id, limit))
                rows = cursor.fetchall()
        else:
            # Get all projects for user and query their usage
            projects = memory.get_projects(user_id=user_id)
            project_ids = [p.get('project_id') for p in projects] if projects else []

            if not project_ids:
                return {"usage": [], "total": 0}

            # Create placeholders for IN clause
            placeholders = ','.join([placeholder] * len(project_ids))
            with db_factory.get_cursor(commit=False) as cursor:
                cursor.execute(f'''
                    SELECT id, project_id, resource_type, quantity, cost_usd, timestamp
                    FROM usage_ledger
                    WHERE project_id IN ({placeholders})
                    ORDER BY timestamp DESC
                    LIMIT {placeholder}
                ''', (*project_ids, limit))
                rows = cursor.fetchall()

        # Convert to list of dicts
        usage_records = []
        for row in rows:
            usage_records.append({
                "id": row[0],
                "project_id": row[1],
                "resource_type": row[2],
                "quantity": row[3],
                "cost_usd": row[4],
                "timestamp": row[5]
            })

        return {
            "usage": usage_records,
            "total": len(usage_records)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching usage records: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch usage records")

@app.get("/api/context/{context_id}")
async def get_context(context_id: str, user_id: str = Depends(get_current_user)):
"""
Retrieve context status for async task polling.

    Returns context with task status and result (if completed).
    """
    try:
        context = context_manager.get_context(context_id)

        if not context:
            raise HTTPException(status_code=404, detail="Context not found or expired")

        # Verify user owns this context (security)
        if context.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        return {
            "context_id": context.context_id,
            "project_id": context.project_id,
            "user_id": context.user_id,
            "created_at": context.created_at.isoformat(),
            "expires_at": context.expires_at.isoformat(),
            "data": context.data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving context {context_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve context")

@app.post("/api/run")
async def run_command(
payload: AgentInput,
user_id: str = Depends(get_current_user),
background_tasks: BackgroundTasks = BackgroundTasks()
):
"""
The Single Entry Point with Safety Net.

    Data Flow:
    1. Receives AgentInput packet from frontend
    2. Authenticates user via JWT token (user_id derived from token)
    3. For heavy tasks: Executes in background (non-blocking) if background_tasks available
    4. For light tasks: Executes synchronously (existing behavior)
    5. Dispatches to Kernel which resolves agent via Registry
    6. Kernel loads DNA config and executes agent
    7. Agent saves snapshot and returns AgentOutput
    8. Always returns HTTP 200 with structured JSON (never 500)
    9. Frontend can always display the result, even on errors

    This endpoint is wrapped in comprehensive error handling to ensure
    the frontend never sees a 500 error and can always display logs.
    """
    try:
        # Override user_id from token (security: never trust client-supplied user_id)
        payload.user_id = user_id

        # Validate params against task schema (return 400 before sync or async path)
        agent_key = kernel._resolve_agent(payload.task)
        if agent_key:
            schema_class = TASK_SCHEMA_MAP.get(agent_key)
            if schema_class is not None:
                try:
                    schema_class.model_validate(payload.params or {})
                except ValidationError as e:
                    logger.warning(f"Params validation failed for task {payload.task}: {e}")
                    raise HTTPException(status_code=400, detail=e.errors())

        # Define heavy tasks that should run in background
        HEAVY_TASKS = ["sniper_agent", "sales_agent", "reactivator_agent", "scout_anchors", "strategist_run"]

        # Map manager actions to heavy tasks (for async execution)
        MANAGER_HEAVY_ACTIONS = {
            "lead_gen_manager": ["hunt_sniper", "ignite_reactivation", "instant_call"],
            # Add other managers if needed
        }

        # Check if task is heavy OR if manager action maps to heavy task
        current_action = payload.params.get("action")
        is_heavy = (
            payload.task in HEAVY_TASKS or
            current_action in MANAGER_HEAVY_ACTIONS.get(payload.task, [])
        )

        # If heavy task and background_tasks available, execute in background
        if is_heavy and background_tasks:
            # Try to get project_id for context creation
            project_id = payload.params.get("project_id") or payload.params.get("niche")
            if not project_id:
                # Try to get from user's active project
                try:
                    project = memory.get_user_project(user_id)
                    if project:
                        project_id = project.get('project_id')
                except Exception as e:
                    logger.debug(f"Could not get user project for context: {e}")

            # Create context if project_id available
            context = None
            if project_id:
                try:
                    context = context_manager.create_context(
                        project_id=project_id,
                        user_id=user_id,
                        initial_data={"request_id": payload.request_id},
                        ttl_seconds=3600
                    )
                    payload.params["context_id"] = context.context_id
                except Exception as e:
                    logger.warning(f"Failed to create context: {e}", exc_info=True)

            # Define background task wrapper
            async def run_agent_background():
                context_id_to_update = context.context_id if context else None
                try:
                    result = await kernel.dispatch(payload)
                    logger.info(f"Background task {payload.task} completed: {result.status}")

                    # Update context with result if context was created
                    if context_id_to_update:
                        try:
                            context_manager.update_context(
                                context_id_to_update,
                                {
                                    "status": "completed",
                                    "result": result.dict()
                                },
                                extend_ttl=False  # Don't extend, task is done
                            )
                            logger.debug(f"Updated context {context_id_to_update} with result")
                        except Exception as e:
                            logger.error(f"Failed to update context with result: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Background task {payload.task} failed: {e}", exc_info=True)

                    # Update context with error if context was created
                    if context_id_to_update:
                        try:
                            from backend.core.models import AgentOutput
                            error_result = AgentOutput(
                                status="error",
                                message=f"Task failed: {str(e)}"
                            )
                            context_manager.update_context(
                                context_id_to_update,
                                {
                                    "status": "failed",
                                    "result": error_result.dict()
                                },
                                extend_ttl=False
                            )
                            logger.debug(f"Updated context {context_id_to_update} with error")
                        except Exception as update_error:
                            logger.error(f"Failed to update context with error: {update_error}", exc_info=True)

            # Schedule background task
            background_tasks.add_task(run_agent_background)
            logger.info(f"📡 Scheduled heavy task '{payload.task}' for background execution")

            # Return immediately
            return {
                "status": "processing",
                "data": {
                    "context_id": context.context_id if context else None,
                    "task": payload.task
                },
                "message": f"Task '{payload.task}' is processing in background",
                "timestamp": datetime.now().isoformat(),
                "error_details": None
            }

        # Light tasks or no background_tasks: Execute synchronously (existing behavior)
        result = await kernel.dispatch(payload)

        # Sanitize response - only return safe fields, not full dict
        return {
            "status": result.status,
            "data": result.data,
            "message": result.message,
            "timestamp": result.timestamp.isoformat() if hasattr(result.timestamp, 'isoformat') else str(result.timestamp),
            "error_details": None
        }
    except ValidationError as e:
        logger.warning(f"Params validation failed in /api/run: {e}")
        raise HTTPException(status_code=400, detail=e.errors())
    except ImportError as e:
        # Catch missing dependencies (e.g., ChromaDB not installed)
        error_trace = traceback.format_exc()
        logger.error(f"ImportError in /api/run: {e}\n{error_trace}")
        return {
            "status": "error",
            "data": None,
            "message": "Internal server error. Please try again later.",
            "timestamp": datetime.now().isoformat(),
            "error_details": None
        }
    except Exception as e:
        # Catch all other exceptions (logic crashes, etc.)
        error_trace = traceback.format_exc()
        logger.error(f"Exception in /api/run: {e}\n{error_trace}")
        return {
            "status": "error",
            "data": None,
            "message": "Internal server error. Please try again later.",
            "timestamp": datetime.now().isoformat(),
            "error_details": None
        }

# Authentication endpoint

class AuthRequest(BaseModel):
email: str
password: str

class AuthResponse(BaseModel):
success: bool
user_id: Optional[str] = None

class AuthResponseWithToken(AuthResponse):
"""Extended response with JWT token."""
token: Optional[str] = None

@app.post("/api/auth/verify", response_model=AuthResponseWithToken)
async def verify_auth(request: AuthRequest):
"""Verify user credentials and return JWT token."""
try: # Trim whitespace from inputs
email = request.email.strip()
password = request.password.strip()

        # Validate inputs
        if not email or not password:
            logger.warning("Auth failed: empty email or password")
            return AuthResponseWithToken(success=False, user_id=None, token=None)

        logger.info(f"Verifying user: {email}")

        # Verify credentials using auth provider (SQLite now, Supabase-ready)
        user_id = verify_user_credentials(email, password)

        if user_id:
            # Create JWT token
            token = create_access_token(user_id)
            logger.info(f"Auth success: {email}")
            return AuthResponseWithToken(success=True, user_id=user_id, token=token)

        logger.warning(f"Auth failed: credentials don't match for {email}")
        return AuthResponseWithToken(success=False, user_id=None, token=None)
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Auth error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Authentication failed. Please try again.")

@app.post("/api/auth/register", response_model=AuthResponse)
async def register_user(request: AuthRequest):
"""Register a new user."""
try: # Trim whitespace from inputs
email = request.email.strip()
password = request.password.strip()

        # Validate inputs
        if not email or not password:
            logger.warning("Registration failed: empty email or password")
            return AuthResponse(success=False, user_id=None)

        logger.info(f"Registering user: {email}")

        success = memory.create_user(email, password)

        if success:
            logger.info(f"Registration success: {email}")
            return AuthResponse(success=True, user_id=email)
        else:
            logger.warning(f"Registration failed: user {email} already exists")
            return AuthResponse(success=False, user_id=None)
    except Exception as e:
        logger.error(f"Registration error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Entities endpoints

@app.get("/api/entities")
async def get_entities(
entity_type: Optional[str] = None,
project_id: Optional[str] = None,
user_id: str = Depends(get_current_user)
):
"""Get entities from SQL database for a specific user (RLS enforced)."""
try: # Verify project ownership if project_id provided
if project_id and not memory.verify_project_ownership(user_id, project_id):
raise HTTPException(status_code=403, detail="Project not found or access denied")

        entities = memory.get_entities(tenant_id=user_id, entity_type=entity_type, project_id=project_id)
        return {"entities": entities}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Entities error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch entities")

class EntityCreateInput(BaseModel):
entity_type: str
name: str
primary_contact: Optional[str] = None
metadata: Dict[str, Any] = {}
project_id: Optional[str] = None

class EntityUpdateInput(BaseModel):
name: Optional[str] = None
primary_contact: Optional[str] = None
metadata: Optional[Dict[str, Any]] = None

@app.post("/api/entities")
async def create_entity(
request: EntityCreateInput,
user_id: str = Depends(get_current_user)
):
"""Create a new entity."""
try: # Verify project ownership if project_id provided
if request.project_id and not memory.verify_project_ownership(user_id, request.project_id):
raise HTTPException(status_code=403, detail="Project not found or access denied")

        entity = Entity(
            tenant_id=user_id,  # Use authenticated user_id
            entity_type=request.entity_type,
            name=request.name,
            primary_contact=request.primary_contact,
            metadata=request.metadata
        )
        success = memory.save_entity(entity, project_id=request.project_id)
        if success:
            logger.info(f"Created entity: {entity.id} of type {request.entity_type} for user {user_id}")
            return {"success": True, "entity": entity.dict()}
        else:
            raise HTTPException(status_code=500, detail="Failed to save entity")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create entity error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create entity")

@app.put("/api/entities/{entity_id}")
async def update_entity_endpoint(
entity_id: str,
request: EntityUpdateInput,
user_id: str = Depends(get_current_user)
):
"""Update an existing entity (RLS enforced)."""
try: # Verify entity belongs to user using direct SQL check
try:
db_factory = get_db_factory(db_path=memory.db_path)
placeholder = db_factory.get_placeholder()
conn = db_factory.get_connection()
db_factory.set_row_factory(conn)
try:
cursor = db_factory.get_cursor_with_row_factory(conn)
cursor.execute(
f"SELECT \* FROM entities WHERE id = {placeholder} AND tenant_id = {placeholder}",
(entity_id, user_id)
)
row = cursor.fetchone()
if not row:
raise HTTPException(status_code=404, detail="Entity not found or access denied")
entity = dict(row)
try:
entity['metadata'] = json.loads(entity['metadata'])
except (json.JSONDecodeError, TypeError):
entity['metadata'] = {}
finally:
cursor.close()
conn.close()
except HTTPException:
raise
except Exception as e:
logger.error(f"Error verifying entity ownership: {e}", exc_info=True)
raise HTTPException(status_code=500, detail="Failed to verify entity ownership")

        # Build update metadata - combine all fields into metadata for update_entity
        update_metadata = {}
        if request.name is not None:
            update_metadata["_name"] = request.name  # Special key for name update
        if request.primary_contact is not None:
            update_metadata["_primary_contact"] = request.primary_contact  # Special key
        if request.metadata:
            update_metadata.update(request.metadata)

        # Update name and primary_contact directly via SQL if provided
        if request.name is not None or request.primary_contact is not None:
            try:
                logger.debug(f"Updating entity {entity_id} name/contact via direct SQL for user {user_id}")
                db_factory = get_db_factory(db_path=memory.db_path)
                placeholder = db_factory.get_placeholder()
                with db_factory.get_cursor() as cursor:
                    if request.name is not None and request.primary_contact is not None:
                        cursor.execute(
                            f"UPDATE entities SET name = {placeholder}, primary_contact = {placeholder} WHERE id = {placeholder} AND tenant_id = {placeholder}",
                            (request.name, request.primary_contact, entity_id, user_id)
                        )
                    elif request.name is not None:
                        cursor.execute(
                            f"UPDATE entities SET name = {placeholder} WHERE id = {placeholder} AND tenant_id = {placeholder}",
                            (request.name, entity_id, user_id)
                        )
                    elif request.primary_contact is not None:
                        cursor.execute(
                            f"UPDATE entities SET primary_contact = {placeholder} WHERE id = {placeholder} AND tenant_id = {placeholder}",
                            (request.primary_contact, entity_id, user_id)
                        )
                logger.debug(f"Successfully updated entity {entity_id} name/contact via direct SQL")
            except Exception as e:
                logger.error(f"Database error updating entity {entity_id} name/contact: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

        # Update metadata if provided
        if request.metadata:
            # Remove special keys from metadata before updating
            clean_metadata = {k: v for k, v in request.metadata.items() if not k.startswith("_")}
            if clean_metadata:
                success = memory.update_entity(entity_id, clean_metadata)
                if not success:
                    raise HTTPException(status_code=500, detail="Failed to update entity metadata")

        logger.info(f"Updated entity: {entity_id} for user {user_id}")
        return {"success": True, "message": "Entity updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update entity error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/entities/{entity_id}")
async def delete_entity_endpoint(
entity_id: str,
user_id: str = Depends(get_current_user)
):
"""Delete an entity (RLS enforced)."""
try:
success = memory.delete_entity(entity_id, user_id)
if success:
logger.info(f"Deleted entity: {entity_id} for user {user_id}")
return {"success": True, "message": "Entity deleted successfully"}
else:
raise HTTPException(status_code=404, detail="Entity not found or access denied")
except HTTPException:
raise
except Exception as e:
logger.error(f"Delete entity error: {e}", exc_info=True)
raise HTTPException(status_code=500, detail="Failed to delete entity")

# Lead capture endpoints

class LeadInput(BaseModel):
project_id: str
source: str # e.g., "Bail Calc - Auckland Central"
data: Dict[str, Any] # Flexible dictionary for captured form data

class LeadResponse(BaseModel):
success: bool
lead_id: Optional[str] = None
message: str = "Lead captured successfully"

@app.post("/api/leads", response_model=LeadResponse)
async def create_lead(
request: LeadInput,
user_id: str = Depends(get_current_user)
):
"""Capture a lead from calculator/contact form and save to SQLite."""
try: # Verify project ownership
if not memory.verify_project_ownership(user_id, request.project_id):
raise HTTPException(status_code=403, detail="Project not found or access denied")

        # Create Entity for lead
        lead_entity = Entity(
            tenant_id=user_id,  # Use authenticated user_id
            entity_type="lead",
            name=request.source,
            metadata=request.data
        )

        # Save to database with project_id
        success = memory.save_entity(lead_entity, project_id=request.project_id)

        if success:
            logger.info(f"Captured lead: {request.source} for user {user_id}, project {request.project_id}")
            return LeadResponse(success=True, lead_id=lead_entity.id, message="Lead captured successfully")
        else:
            raise HTTPException(status_code=500, detail="Failed to save lead")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Leads error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to capture lead")

@app.get("/api/leads")
async def get_leads(user_id: str = Depends(get_current_user)):
"""Get all leads for a specific user (RLS enforced)."""
try:
leads = memory.get_entities(tenant_id=user_id, entity_type="lead")
return {"leads": leads}
except Exception as e:
logger.error(f"Error fetching leads: {e}", exc_info=True)
raise HTTPException(status_code=500, detail="Failed to fetch leads")

# Projects endpoint

class ProjectInput(BaseModel):
name: str
niche: str

class ProjectResponse(BaseModel):
success: bool
project_id: str
message: str = "Project created successfully"

@app.post("/api/projects", response*model=ProjectResponse)
async def create_project(
request: ProjectInput,
background_tasks: BackgroundTasks,
user_id: str = Depends(get_current_user)
):
"""Create a new project and trigger onboarding agent."""
try: # Generate project_id from niche (sanitize for filesystem)
project_id = re.sub(r'[^a-zA-Z0-9*-]', '\_', request.niche.lower())

        # Register project in database
        memory.register_project(
            user_id=user_id,  # Use authenticated user_id
            project_id=project_id,
            niche=request.name
        )

        logger.info(f"Created project: {project_id} for user {user_id}")

        # Automatically trigger onboarding agent in background
        async def trigger_onboarding():
            try:
                onboarding_input = AgentInput(
                    task="onboarding",
                    user_id=user_id,  # Use authenticated user_id
                    params={
                        "niche": project_id,
                        "message": "",
                        "history": ""
                    }
                )
                await kernel.dispatch(onboarding_input)
                logger.info(f"Onboarding agent completed for project {project_id}")
            except Exception as e:
                logger.error(f"Onboarding agent error for project {project_id}: {e}", exc_info=True)

        background_tasks.add_task(trigger_onboarding)
        logger.info(f"Triggered onboarding agent for project {project_id}")

        return ProjectResponse(
            success=True,
            project_id=project_id,
            message="Project created and onboarding started"
        )
    except Exception as e:
        logger.error(f"Projects error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create project")

@app.get("/api/projects")
async def get_projects(user_id: str = Depends(get_current_user)):
"""Get all projects for a specific user."""
try:
projects = memory.get_projects(user_id=user_id)
return {"projects": projects}
except Exception as e:
logger.error(f"Error fetching projects: {e}", exc_info=True)
raise HTTPException(status_code=500, detail="Failed to fetch projects")

# Settings endpoints

class SettingsInput(BaseModel):
wp_url: str
wp_user: str
wp_password: str

@app.get("/api/settings")
async def get_settings(user_id: str = Depends(get_current_user)):
"""Get WordPress credentials for a user."""
try:
secrets = memory.get_client_secrets(user_id)
if secrets:
return {
"wp_url": secrets.get("wp_url", ""),
"wp_user": secrets.get("wp_user", ""),
"wp_password": "" # Never return password in API
}
return {
"wp_url": "",
"wp_user": "",
"wp_password": ""
}
except Exception as e:
logger.error(f"Get settings error: {e}", exc_info=True)
raise HTTPException(status_code=500, detail="Failed to fetch settings")

@app.post("/api/settings")
async def save_settings(
request: SettingsInput,
user_id: str = Depends(get_current_user)
):
"""Save WordPress credentials for a user."""
try:
success = memory.save_client_secrets(
user_id=user_id, # Use authenticated user_id
wp_url=request.wp_url,
wp_user=request.wp_user,
wp_password=request.wp_password
)
if success:
logger.info(f"Saved settings for user {user_id}")
return {"success": True, "message": "Settings saved successfully"}
else:
raise HTTPException(status_code=500, detail="Failed to save settings")
except HTTPException:
raise
except Exception as e:
logger.error(f"Save settings error: {e}", exc_info=True)
raise HTTPException(status_code=500, detail="Failed to save settings")

# DNA Config endpoints

@app.get("/api/projects/{project_id}/dna")
async def get_dna_config(
project_id: str,
user_id: str = Depends(get_current_user)
):
"""Get DNA configuration for a project."""
try: # Verify project ownership
if not memory.verify_project_ownership(user_id, project_id):
raise HTTPException(status_code=403, detail="Project not found or access denied")

        # Load config using ConfigLoader
        from backend.core.config import ConfigLoader
        config_loader = ConfigLoader()
        config = config_loader.load(project_id)

        if "error" in config:
            raise HTTPException(status_code=404, detail=config.get("error", "Config not found"))

        return {"config": config}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get DNA config error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load DNA configuration")

@app.put("/api/projects/{project_id}/dna")
async def update_dna_config(
project_id: str,
config: Dict[str, Any],
user_id: str = Depends(get_current_user)
):
"""Update DNA configuration for a project (writes to dna.custom.yaml)."""
try: # Verify project ownership
if not memory.verify_project_ownership(user_id, project_id):
raise HTTPException(status_code=403, detail="Project not found or access denied")

        # Get profile path
        from backend.core.config import ConfigLoader
        config_loader = ConfigLoader()
        profile_path = os.path.join(config_loader.profiles_dir, project_id)

        # Ensure directory exists
        os.makedirs(profile_path, exist_ok=True)

        # Write to dna.custom.yaml
        custom_path = os.path.join(profile_path, "dna.custom.yaml")
        with open(custom_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Updated DNA config for project {project_id} by user {user_id}")
        return {"success": True, "message": "DNA configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update DNA config error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update DNA configuration")

@app.get("/api/projects/{project_id}/campaigns")
async def get_campaigns(
project_id: str,
module: Optional[str] = None, # Query param: ?module=pseo
user_id: str = Depends(get_current_user)
):
"""Get campaigns for a project, optionally filtered by module."""
try:
if not memory.verify_project_ownership(user_id, project_id):
raise HTTPException(status_code=403, detail="Project not found or access denied")

        campaigns = memory.get_campaigns_by_project(user_id, project_id, module=module)
        return {"campaigns": campaigns}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching campaigns: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch campaigns")

# System monitoring endpoints

@app.get("/api/logs")
async def get_logs(
lines: int = 50,
user_id: str = Depends(get_current_user)
):
"""Get the last N lines from the system log file."""
try:
log_file_path = os.path.join(BASE_DIR, "logs", "apex.log")

        if not os.path.exists(log_file_path):
            return {
                "logs": [],
                "total_lines": 0,
                "message": "Log file not found"
            }

        # Read last N lines from file
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        # Remove trailing newlines and return
        cleaned_lines = [line.rstrip('\n\r') for line in last_lines]

        return {
            "logs": cleaned_lines,
            "total_lines": len(cleaned_lines)
        }
    except Exception as e:
        logger.error(f"Error reading logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to read logs")

# Include voice router

app.include_router(voice_router, prefix="/api/voice", tags=["voice"])
app.include_router(webhook_router, prefix="/api/webhooks", tags=["webhooks"])

if **name** == "**main**": # Dev Mode: Runs on localhost:8000
uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

## FILE: backend/core/**init**.py

## FILE: backend/core/agent_base.py

# backend/core/agent_base.py

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging
import traceback
import json
import os
from datetime import datetime
from backend.core.models import AgentInput, AgentOutput

class BaseAgent(ABC):
def **init**(self, name: str, config: Dict[str, Any] = None):
self.name = name
self.config = config or {}
self.project_id: Optional[str] = None # Injected by kernel
self.user_id: Optional[str] = None # Injected by kernel
self.campaign_id: Optional[str] = None # Injected by kernel (if campaign-scoped)
self.logger = logging.getLogger(f"Apex.{name}")

    def log(self, message: str):
        self.logger.info(message)

    def save_snapshot(self, step_name: str, input_data: AgentInput, output_data: Optional[AgentOutput] = None, error_traceback: Optional[str] = None):
        """
        Saves a snapshot of agent execution to logs/snapshots/ for debugging.

        Data Flow: This method captures the complete state of an agent execution,
        including inputs, outputs, and any errors. This allows debugging the "black box"
        by examining JSON files after execution.

        Args:
            step_name: "start" or "end" to indicate when the snapshot was taken
            input_data: The AgentInput packet received from Kernel
            output_data: The AgentOutput returned (None for "start" snapshots)
            error_traceback: Full traceback string if an error occurred
        """
        try:
            # Ensure logs/snapshots directory exists
            snapshot_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "snapshots")
            os.makedirs(snapshot_dir, exist_ok=True)

            # Create timestamp for filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
            filename = f"{timestamp}_{self.name}_{step_name}.json"
            filepath = os.path.join(snapshot_dir, filename)

            # Build snapshot data
            snapshot = {
                "timestamp": datetime.now().isoformat(),
                "agent_name": self.name,
                "step": step_name,
                "input_context": {
                    "task": input_data.task,
                    "user_id": input_data.user_id,
                    "request_id": input_data.request_id,
                    "params": input_data.params
                },
                "output_result": output_data.dict() if output_data else None,
                "error_traceback": error_traceback
            }

            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2, default=str)

            self.logger.debug(f"Snapshot saved: {filename}")
        except Exception as e:
            # Don't let snapshot failures break the agent execution
            self.logger.warning(f"Failed to save snapshot: {e}")

    async def run(self, input_data: AgentInput) -> AgentOutput:
        """
        The entry point for all agents with automatic logging and snapshot recording.

        Data Flow:
        1. Receives AgentInput packet from Kernel (via /api/run endpoint)
        2. Saves "start" snapshot with input data
        3. Calls _execute() (agent-specific logic implemented by each agent)
        4. Saves "end" snapshot with input and output data
        5. Returns AgentOutput to Kernel, which returns it to the frontend

        This method wraps _execute() with logging, error handling, and snapshot recording.
        """
        self.logger.info(f"Agent Started: {self.name}")

        # Save snapshot at start of execution
        # TEMPORARILY DISABLED: Commented out until needed for debugging
        # self.save_snapshot("start", input_data, None)

        try:
            # Call the abstract method that each agent implements
            result = await self._execute(input_data)

            # Log successful completion
            self.logger.info(f"Agent Finished: {self.name} - Status: {result.status}")

            # Save snapshot at end of successful execution
            # TEMPORARILY DISABLED: Commented out until needed for debugging
            # self.save_snapshot("end", input_data, result, None)

            return result

        except Exception as e:
            # Log full traceback to file (logger.exception() includes stack trace)
            self.logger.exception(f"Agent Failed: {self.name} - {str(e)}")

            # Capture full traceback for snapshot
            error_trace = traceback.format_exc()

            # Return error output
            error_result = AgentOutput(
                status="error",
                message=f"Agent {self.name} failed: {str(e)}"
            )

            # Save snapshot at end of failed execution
            # TEMPORARILY DISABLED: Commented out until needed for debugging
            # self.save_snapshot("end", input_data, error_result, error_trace)

            return error_result

    @abstractmethod
    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Every agent must implement this function.
        It takes the Universal Packet (Input) and returns the Universal Receipt (Output).
        This is called by run() which provides logging and error handling.
        """
        pass

## FILE: backend/core/auth.py

# backend/core/auth.py

"""
Authentication abstraction layer.

Current implementation: JWT with SQLite user store
Future: Can be swapped to Supabase Auth with minimal changes to API

This abstraction allows switching from SQLite to Supabase without changing
the FastAPI endpoints - only the AuthProvider implementation changes.
"""
import os
import jwt
import logging
from typing import Optional
from datetime import datetime, timedelta
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.core.memory import memory

logger = logging.getLogger("Apex.Auth")

# Security scheme

security = HTTPBearer()

# JWT Configuration (can be moved to env/config later)

\_jwt_secret = os.getenv("APEX_JWT_SECRET") or os.getenv("JWT_SECRET")
if not \_jwt_secret:
raise ValueError("APEX_JWT_SECRET or JWT_SECRET environment variable must be set. Cannot start without a secure JWT secret.")
JWT_SECRET = \_jwt_secret
JWT_ALGORITHM = os.getenv("APEX_JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_HOURS = int(os.getenv("APEX_JWT_EXPIRATION_HOURS", "24"))

class AuthProvider:
"""
Abstract authentication provider interface.

    Current: SQLiteAuthProvider (uses memory.py)
    Future: SupabaseAuthProvider (uses Supabase Auth)
    """

    def verify_credentials(self, email: str, password: str) -> Optional[str]:
        """
        Verify user credentials and return user_id if valid.

        Returns:
            user_id (str) if valid, None otherwise
        """
        raise NotImplementedError

    def get_user_id_from_token(self, token: str) -> Optional[str]:
        """
        Extract and verify user_id from JWT token.

        Returns:
            user_id (str) if valid, None otherwise
        """
        raise NotImplementedError

    def create_token(self, user_id: str) -> str:
        """
        Create JWT token for user.

        Args:
            user_id: The user identifier

        Returns:
            JWT token string
        """
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

class SQLiteAuthProvider(AuthProvider):
"""
Current implementation: SQLite-backed authentication.
Uses memory.py for user storage and verification.

    To migrate to Supabase:
    1. Create SupabaseAuthProvider class
    2. Implement verify_credentials() using Supabase Auth API
    3. Implement get_user_id_from_token() using Supabase JWT verification
    4. Swap provider instance in get_auth_provider()
    """

    def verify_credentials(self, email: str, password: str) -> Optional[str]:
        """Verify against SQLite user store."""
        if memory.verify_user(email, password):
            return email  # user_id is email in SQLite implementation
        return None

    def get_user_id_from_token(self, token: str) -> Optional[str]:
        """
        Verify JWT and extract user_id.

        Future: When using Supabase, this would:
        1. Verify token signature with Supabase JWT secret
        2. Extract user_id from Supabase claims
        3. Optionally verify token hasn't been revoked in Supabase
        """
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("user_id")

            # Verify user still exists (SQLite check)
            # Future: Supabase would verify against Supabase Auth user pool
            if user_id and memory._user_exists(user_id):
                return user_id
            return None
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
        except Exception as e:
            logger.error(f"Token verification error: {e}", exc_info=True)
            return None

# Singleton provider instance (swapable for Supabase migration)

\_auth_provider: Optional[AuthProvider] = None

def get_auth_provider() -> AuthProvider:
"""
Get the current authentication provider.

    Current: SQLiteAuthProvider
    Future: Swap to SupabaseAuthProvider by changing this function:

        def get_auth_provider() -> AuthProvider:
            return SupabaseAuthProvider()
    """
    global _auth_provider
    if _auth_provider is None:
        _auth_provider = SQLiteAuthProvider()
    return _auth_provider

async def get_current_user(
credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
"""
FastAPI dependency to extract authenticated user_id from JWT token.

    Usage in endpoints:
        @app.get("/api/protected")
        async def protected_route(user_id: str = Depends(get_current_user)):
            # user_id is guaranteed to be valid
    """
    token = credentials.credentials
    provider = get_auth_provider()

    user_id = provider.get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token"
        )

    return user_id

def create_access_token(user_id: str) -> str:
"""Create JWT access token for user."""
provider = get_auth_provider()
return provider.create_token(user_id)

def verify_user_credentials(email: str, password: str) -> Optional[str]:
"""
Verify user credentials and return user_id if valid.

    Used by login endpoint.
    """
    provider = get_auth_provider()
    return provider.verify_credentials(email, password)

## FILE: backend/core/config.py

# backend/core/config.py

import yaml
import os
import logging
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from dotenv import load_dotenv

logger = logging.getLogger("Apex.Config")

# Environment Variables Settings (using Pydantic BaseSettings)

# Calculate project root (three levels up from backend/core/config.py) for .env file path

\_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(**file**))))
\_ENV_FILE_PATH = os.path.join(\_BASE_DIR, ".env")

# Ensure .env is loaded into environment before Pydantic Settings reads it

# This is critical when called from threads (asyncio.to_thread)

load_dotenv(dotenv_path=\_ENV_FILE_PATH, override=True)

# Debug: Verify .env was loaded

\_env_key = os.getenv("SERPER_API_KEY")
if \_env_key:
logger.debug(f"✅ .env loaded: SERPER_API_KEY found in os.environ (length: {len(\_env_key)})")
else:
logger.warning(f"⚠️ .env not loaded: SERPER_API_KEY not in os.environ. .env path: {\_ENV_FILE_PATH}, exists: {os.path.exists(\_ENV_FILE_PATH)}")

class Settings(BaseSettings):
"""
Application settings loaded from environment variables.
Uses Pydantic BaseSettings for automatic .env file loading.
"""
SERPER_API_KEY: str = ""

    model_config = ConfigDict(
        env_file=_ENV_FILE_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields from .env that aren't defined in this class
    )

# Singleton settings instance

settings = Settings()

# Fallback: If Pydantic didn't load it, manually parse .env file and set os.environ

if not settings.SERPER_API_KEY: # Manual .env parser as ultimate fallback
\_manual_value = None
if os.path.exists(\_ENV_FILE_PATH):
try:
with open(\_ENV_FILE_PATH, 'r') as f:
for line in f:
line = line.strip() # Skip comments and empty lines
if not line or line.startswith('#'):
continue # Parse KEY=VALUE format
if '=' in line:
key, value = line.split('=', 1)
key = key.strip()
value = value.strip() # Remove quotes if present
if value.startswith('"') and value.endswith('"'):
value = value[1:-1]
elif value.startswith("'") and value.endswith("'"):
value = value[1:-1] # Set in os.environ
os.environ[key] = value
if key == "SERPER_API_KEY":
\_manual_value = value
logger.info(f"✅ Manually loaded SERPER_API_KEY from .env file (length: {len(value)})")
except Exception as e:
logger.error(f"❌ Error manually parsing .env file: {e}")

    # Now recreate Settings (should pick up from os.environ)
    if _manual_value:
        settings = Settings()
        # If still empty, create with explicit value
        if not settings.SERPER_API_KEY:
            settings = Settings(SERPER_API_KEY=_manual_value)
            logger.info(f"✅ Settings: SERPER_API_KEY loaded via manual parser (length: {len(_manual_value)})")
    else:
        logger.error(f"❌ SERPER_API_KEY not found in .env file! .env path: {_ENV_FILE_PATH}, exists: {os.path.exists(_ENV_FILE_PATH)}")

if settings.SERPER_API_KEY:
logger.debug(f"✅ Settings: SERPER_API_KEY loaded (length: {len(settings.SERPER_API_KEY)})")
else:
logger.warning(f"⚠️ Settings: SERPER_API_KEY is empty! .env path: {\_ENV_FILE_PATH}, exists: {os.path.exists(\_ENV_FILE_PATH)}")

class ConfigLoader:
def **init**(self, profiles_dir="data/profiles"):
self.profiles_dir = profiles_dir
self.logger = logging.getLogger("Apex.Config")

    def load(self, project_id: str, campaign_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Loads DNA + campaign config (if campaign_id provided) and merges them.
        Merges: Defaults -> Generated DNA -> Custom Overrides -> Campaign Config

        Args:
            project_id: The project identifier
            campaign_id: Optional campaign identifier. If provided, loads and merges campaign config.

        Returns:
            Merged configuration dictionary
        """
        self.logger.debug(f"Loading config for project {project_id}, campaign {campaign_id}")

        # 1. Load DNA (base configuration)
        dna = self.load_dna(project_id)
        if dna.get("error"):
            return dna

        # 2. If campaign_id provided, load and merge campaign config
        if campaign_id:
            campaign_config = self.load_campaign_config(campaign_id)
            if campaign_config:
                merged = self.merge_config(dna, campaign_config)
                self.logger.debug(f"Successfully merged DNA + campaign config for campaign {campaign_id}")
                return merged
            else:
                self.logger.warning(f"Campaign {campaign_id} not found, returning DNA only")

        return dna

    def load_dna(self, project_id: str) -> Dict[str, Any]:
        """
        Loads only the DNA (project-level configuration).
        Merges: Defaults -> Generated DNA -> Custom Overrides

        Args:
            project_id: The project identifier

        Returns:
            DNA configuration dictionary
        """
        self.logger.debug(f"Loading DNA for project: {project_id}")

        # 1. System Defaults
        config = {"system_currency": "NZD", "timezone": "Pacific/Auckland"}

        profile_path = os.path.join(self.profiles_dir, project_id)

        # 2. Safety Check
        if not os.path.exists(profile_path):
            self.logger.warning(f"Profile path not found: {profile_path} for project: {project_id}")
            return {"error": "Profile not found", "project_id": project_id}

        # 3. Load AI Generated DNA
        gen_path = os.path.join(profile_path, "dna.generated.yaml")
        if os.path.exists(gen_path):
            try:
                with open(gen_path, 'r') as f:
                    loaded_config = yaml.safe_load(f) or {}
                    config.update(loaded_config)
                    self.logger.debug(f"Successfully loaded generated DNA from {gen_path}")
            except yaml.YAMLError as e:
                self.logger.error(f"YAML parsing error in {gen_path}: {e}")
            except FileNotFoundError as e:
                self.logger.error(f"File not found when trying to read {gen_path}: {e}")
            except PermissionError as e:
                self.logger.error(f"Permission denied when reading {gen_path}: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error reading {gen_path}: {e}")

        # 4. Load Human Overrides (Custom Settings) - These win.
        custom_path = os.path.join(profile_path, "dna.custom.yaml")
        if os.path.exists(custom_path):
            try:
                with open(custom_path, 'r') as f:
                    loaded_config = yaml.safe_load(f) or {}
                    config.update(loaded_config)
                    self.logger.debug(f"Successfully loaded custom overrides from {custom_path}")
            except yaml.YAMLError as e:
                self.logger.error(f"YAML parsing error in {custom_path}: {e}")
            except FileNotFoundError as e:
                self.logger.error(f"File not found when trying to read {custom_path}: {e}")
            except PermissionError as e:
                self.logger.error(f"Permission denied when reading {custom_path}: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error reading {custom_path}: {e}")

        self.logger.debug(f"DNA loaded successfully for project: {project_id}")
        return config

    def load_campaign_config(self, campaign_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Loads campaign configuration from database (and disk backup if available).

        Args:
            campaign_id: The campaign identifier
            user_id: Optional user_id for RLS check. If None, loads without RLS (internal use only).

        Returns:
            Campaign configuration dictionary, or None if not found
        """
        self.logger.debug(f"Loading campaign config for campaign: {campaign_id}")

        try:
            from backend.core.memory import memory

            # Try to get campaign from DB
            if user_id:
                campaign = memory.get_campaign(campaign_id, user_id)
            else:
                # Internal use: query directly (bypass RLS)
                # This is safe because we're only reading config, not modifying
                placeholder = memory.db_factory.get_placeholder()
                with memory.db_factory.get_cursor(commit=False) as cursor:
                    cursor.execute(f"SELECT project_id, config FROM campaigns WHERE id = {placeholder}", (campaign_id,))
                    row = cursor.fetchone()
                    if row:
                        project_id, config_json = row
                        import json
                        config = json.loads(config_json) if isinstance(config_json, str) else config_json
                        campaign = {"project_id": project_id, "config": config}
                    else:
                        campaign = None

            if campaign:
                config = campaign.get('config', {})
                project_id = campaign.get('project_id')

                # Also try to load from disk backup
                if project_id:
                    campaign_path = os.path.join(self.profiles_dir, project_id, "campaigns", f"{campaign_id}.yaml")
                    if os.path.exists(campaign_path):
                        try:
                            with open(campaign_path, 'r') as f:
                                disk_config = yaml.safe_load(f) or {}
                                # Merge: DB config takes precedence, but disk can have additional fields
                                config = {**disk_config, **config}
                                self.logger.debug(f"Loaded campaign config from disk backup: {campaign_path}")
                        except Exception as e:
                            self.logger.warning(f"Failed to load campaign config from disk: {e}")

                self.logger.debug(f"Successfully loaded campaign config for campaign: {campaign_id}")
                return config
            else:
                self.logger.warning(f"Campaign {campaign_id} not found in database")
                return None

        except Exception as e:
            self.logger.error(f"Error loading campaign config for {campaign_id}: {e}")
            return None

    def merge_config(self, dna: Dict[str, Any], campaign_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merges DNA (base config) with campaign-specific config.
        Campaign config takes precedence for module-specific settings.

        Args:
            dna: Base DNA configuration
            campaign_config: Campaign-specific configuration

        Returns:
            Merged configuration dictionary
        """
        self.logger.debug("Merging DNA + campaign config")

        # Start with DNA as base
        merged = dna.copy()

        # Campaign config provides module-specific settings
        # Structure: campaign_config contains module config (e.g., targeting, mining_requirements, etc.)
        # We merge it into the appropriate module section

        # Get the module from campaign config (if available) or infer from structure
        module = campaign_config.get('module') or campaign_config.get('_module')

        if module:
            # Ensure modules section exists
            if 'modules' not in merged:
                merged['modules'] = {}
            if module not in merged['modules']:
                merged['modules'][module] = {}

            # Merge campaign config into module section
            # Campaign config structure matches the template (e.g., targeting, mining_requirements, etc.)
            # We merge it into modules.{module}
            merged['modules'][module].update(campaign_config)
        else:
            # If no module specified, merge at top level (campaign config should be module-specific)
            # For safety, merge into a 'campaign' key
            merged['campaign'] = campaign_config

        self.logger.debug("Successfully merged DNA + campaign config")
        return merged

## FILE: backend/core/context.py

# backend/core/context.py

import redis
import json
import os
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

logger = logging.getLogger("Apex.Context")

class AgentContext(BaseModel):
"""
Short-term memory (RAM) for agent communication.
Stored in Redis with TTL for automatic expiration.
"""
context_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique context identifier")
project_id: str = Field(..., description="Project identifier")
user_id: str = Field(..., description="User identifier (tenant)")
created_at: datetime = Field(default_factory=datetime.now, description="Context creation timestamp")
expires_at: datetime = Field(..., description="Context expiration timestamp")
data: Dict[str, Any] = Field(default_factory=dict, description="Flexible key-value store for agent data")

    def extend_ttl(self, seconds: int = 3600):
        """Extend expiration time."""
        self.expires_at = datetime.now() + timedelta(seconds=seconds)

class ContextManager:
"""
Manages agent context in Redis (RAM).
Falls back to in-memory dict if Redis is unavailable.

    Architecture Pattern: Follows MemoryManager and Kernel singleton pattern.
    """
    def __init__(self):
        self.logger = logging.getLogger("Apex.Context")

        # In-memory fallback storage
        self._in_memory_contexts: Dict[str, AgentContext] = {}

        # Try to connect to Redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.default_ttl = int(os.getenv("REDIS_TTL_SECONDS", "3600"))

        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()  # Test connection
            self.enabled = True
            self.logger.info("✅ Redis Context Manager initialized")
        except Exception as e:
            self.logger.warning(f"⚠️ Redis not available: {e}. Context will be disabled.")
            self.redis_client = None
            self.enabled = False
            self.logger.info("⚠️ Using in-memory context (not persistent)")

    def create_context(
        self,
        project_id: str,
        user_id: str,
        initial_data: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None
    ) -> AgentContext:
        """
        Create a new context and store in Redis (or in-memory fallback).

        Args:
            project_id: Project identifier
            user_id: User identifier (tenant)
            initial_data: Optional initial data to store in context
            ttl_seconds: Time-to-live in seconds (defaults to REDIS_TTL_SECONDS or 3600)

        Returns:
            AgentContext with context_id that can be passed to agents
        """
        ttl = ttl_seconds or self.default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl)

        context = AgentContext(
            project_id=project_id,
            user_id=user_id,
            expires_at=expires_at,
            data=initial_data or {}
        )

        if self.enabled:
            # Store in Redis
            try:
                key = f"context:{context.context_id}"
                self.redis_client.setex(
                    key,
                    ttl,
                    json.dumps(context.dict(), default=str)
                )
                self.logger.debug(f"Created context {context.context_id} for project {project_id}")
            except Exception as e:
                self.logger.error(f"Failed to create context in Redis: {e}", exc_info=True)
                # Fall back to in-memory
                self._in_memory_contexts[context.context_id] = context
                self.logger.warning("⚠️ Falled back to in-memory context storage")
        else:
            # Store in-memory
            self._in_memory_contexts[context.context_id] = context

        return context

    def get_context(self, context_id: str) -> Optional[AgentContext]:
        """
        Retrieve context from Redis (or in-memory fallback).

        Args:
            context_id: Context identifier to retrieve

        Returns:
            AgentContext if found and not expired, None otherwise
        """
        if self.enabled:
            # Try Redis first
            try:
                key = f"context:{context_id}"
                data = self.redis_client.get(key)
                if not data:
                    return None

                context_dict = json.loads(data)
                # Convert datetime strings back to datetime objects
                context_dict['created_at'] = datetime.fromisoformat(context_dict['created_at'])
                context_dict['expires_at'] = datetime.fromisoformat(context_dict['expires_at'])

                context = AgentContext(**context_dict)

                # Check if expired
                if context.expires_at < datetime.now():
                    self.delete_context(context_id)
                    return None

                return context
            except Exception as e:
                self.logger.error(f"Failed to get context from Redis: {e}", exc_info=True)
                # Fall back to in-memory
                pass

        # In-memory fallback
        context = self._in_memory_contexts.get(context_id)
        if not context:
            return None

        # Check if expired
        if context.expires_at < datetime.now():
            del self._in_memory_contexts[context_id]
            return None

        return context

    def update_context(
        self,
        context_id: str,
        updates: Dict[str, Any],
        extend_ttl: bool = True
    ) -> bool:
        """
        Update context data and optionally extend TTL.

        Args:
            context_id: Context to update
            updates: Key-value pairs to merge into context.data
            extend_ttl: If True, extend TTL by default_ttl

        Returns:
            True on success, False on error or if context not found
        """
        context = self.get_context(context_id)
        if not context:
            return False

        # Merge updates
        context.data.update(updates)

        # Extend TTL if requested
        if extend_ttl:
            context.extend_ttl(self.default_ttl)

        # Save back
        if self.enabled:
            try:
                key = f"context:{context_id}"
                remaining_ttl = int((context.expires_at - datetime.now()).total_seconds())
                if remaining_ttl > 0:
                    self.redis_client.setex(
                        key,
                        remaining_ttl,
                        json.dumps(context.dict(), default=str)
                    )
                    return True
                return False
            except Exception as e:
                self.logger.error(f"Failed to update context in Redis: {e}", exc_info=True)
                # Fall back to in-memory
                self._in_memory_contexts[context_id] = context
                return True
        else:
            # Update in-memory
            self._in_memory_contexts[context_id] = context
            return True

    def delete_context(self, context_id: str) -> bool:
        """
        Delete context from Redis (or in-memory fallback).

        Args:
            context_id: Context to delete

        Returns:
            True on success, False on error
        """
        if self.enabled:
            try:
                key = f"context:{context_id}"
                self.redis_client.delete(key)
                return True
            except Exception as e:
                self.logger.error(f"Failed to delete context from Redis: {e}", exc_info=True)
                # Fall back to in-memory
                pass

        # In-memory fallback
        if context_id in self._in_memory_contexts:
            del self._in_memory_contexts[context_id]
            return True

        return False

# Singleton

context_manager = ContextManager()

## FILE: backend/core/db.py

# backend/core/db.py

"""
Database Connection Factory for PostgreSQL and SQLite support.

Automatically detects database type from DATABASE_URL environment variable.
If DATABASE_URL is set and starts with postgres:// or postgresql://, uses PostgreSQL.
Otherwise, falls back to SQLite for local development.
"""
import os
import logging
from typing import Optional, Any, Dict
from contextlib import contextmanager

logger = logging.getLogger("ApexDB")

class DatabaseError(Exception):
"""Common exception for database errors."""
pass

class DatabaseFactory:
"""
Factory for creating database connections with unified interface.
Supports both PostgreSQL (via psycopg2) and SQLite.
"""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database factory.

        Args:
            db_path: Path to SQLite database file (only used if DATABASE_URL not set)
        """
        self.db_path = db_path
        self.db_type = self._detect_db_type()
        self.logger = logging.getLogger("ApexDB")

        if self.db_type == "postgresql":
            try:
                import psycopg2
                import psycopg2.extras
                self.psycopg2 = psycopg2
                self.psycopg2_extras = psycopg2.extras
                self.logger.info("✅ Database: PostgreSQL (via psycopg2)")
            except ImportError:
                self.logger.error("❌ psycopg2 not installed. Install with: pip install psycopg2-binary")
                raise ImportError("psycopg2 is required for PostgreSQL support")
        else:
            import sqlite3
            self.sqlite3 = sqlite3
            self.logger.info("✅ Database: SQLite")

    def _detect_db_type(self) -> str:
        """Detect database type from DATABASE_URL environment variable."""
        database_url = os.getenv("DATABASE_URL", "").strip()

        if database_url and (database_url.startswith("postgres://") or
                           database_url.startswith("postgresql://")):
            return "postgresql"
        return "sqlite"

    def get_connection(self):
        """
        Get a database connection.

        Returns:
            Connection object (sqlite3.Connection or psycopg2.connection)
        """
        if self.db_type == "postgresql":
            database_url = os.getenv("DATABASE_URL")
            conn = self.psycopg2.connect(database_url)
            # Enable autocommit for PostgreSQL (similar to SQLite behavior)
            conn.autocommit = False
            return conn
        else:
            # SQLite
            if not self.db_path:
                raise ValueError("db_path must be provided for SQLite")
            return self.sqlite3.connect(self.db_path)

    @contextmanager
    def get_cursor(self, commit: bool = True):
        """
        Context manager for database cursor with automatic cleanup.

        Args:
            commit: Whether to commit transaction on success (default: True)

        Yields:
            Cursor object
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            yield cursor
            if commit:
                conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            # Convert database-specific exceptions to common exception
            if self.db_type == "postgresql":
                import psycopg2
                if isinstance(e, (psycopg2.Error, psycopg2.IntegrityError)):
                    raise DatabaseError(f"Database error: {e}") from e
            else:
                import sqlite3
                if isinstance(e, (sqlite3.Error, sqlite3.IntegrityError)):
                    raise DatabaseError(f"Database error: {e}") from e
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def get_placeholder(self) -> str:
        """Get SQL placeholder for parameterized queries."""
        return "%s" if self.db_type == "postgresql" else "?"

    def get_row_factory(self):
        """
        Get appropriate row factory for the database type.

        Returns:
            Row factory class or None
        """
        if self.db_type == "postgresql":
            return self.psycopg2_extras.RealDictRow
        else:
            return self.sqlite3.Row

    def set_row_factory(self, conn):
        """
        Set row factory on connection.

        Args:
            conn: Database connection object
        """
        if self.db_type == "postgresql":
            # PostgreSQL: RealDictRow is set per cursor, not connection
            # We'll handle this when creating cursors
            pass
        else:
            # SQLite: set row_factory on connection
            conn.row_factory = self.sqlite3.Row

    def get_cursor_with_row_factory(self, conn):
        """
        Get a cursor with appropriate row factory.

        Args:
            conn: Database connection object

        Returns:
            Cursor object with row factory set
        """
        if self.db_type == "postgresql":
            # PostgreSQL: use RealDictRow cursor factory
            return conn.cursor(cursor_factory=self.psycopg2_extras.RealDictRow)
        else:
            # SQLite: row factory is set on connection, just get cursor
            return conn.cursor()

    def get_insert_or_replace_sql(self, table: str, columns: list, primary_key: str) -> str:
        """
        Generate INSERT OR REPLACE SQL that works for both databases.

        Args:
            table: Table name
            columns: List of column names
            primary_key: Primary key column name for ON CONFLICT clause

        Returns:
            SQL statement string
        """
        placeholders = [self.get_placeholder()] * len(columns)
        cols_str = ", ".join(columns)
        vals_str = ", ".join(placeholders)

        if self.db_type == "postgresql":
            # PostgreSQL: INSERT ... ON CONFLICT ... DO UPDATE
            update_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in columns])
            return f"""
                INSERT INTO {table} ({cols_str})
                VALUES ({vals_str})
                ON CONFLICT ({primary_key}) DO UPDATE SET {update_clause}
            """
        else:
            # SQLite: INSERT OR REPLACE
            return f"INSERT OR REPLACE INTO {table} ({cols_str}) VALUES ({vals_str})"

    def get_date_start_of_month(self) -> str:
        """
        Get SQL expression for start of current month.

        Returns:
            SQL expression string
        """
        if self.db_type == "postgresql":
            return "date_trunc('month', CURRENT_DATE)"
        else:
            return "date('now', 'start of month')"

    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL."""
        return self.db_type == "postgresql"

    def is_sqlite(self) -> bool:
        """Check if using SQLite."""
        return self.db_type == "sqlite"

    def get_json_type(self) -> str:
        """
        Get appropriate JSON column type for the database.

        Returns:
            Type string (JSONB for PostgreSQL, TEXT for SQLite)
        """
        if self.db_type == "postgresql":
            return "JSONB"  # PostgreSQL: JSONB is more efficient than JSON
        else:
            return "TEXT"  # SQLite: JSON stored as TEXT

# Global factory instance (will be initialized by MemoryManager)

\_db_factory: Optional[DatabaseFactory] = None

def get_db_factory(db_path: Optional[str] = None) -> DatabaseFactory:
"""
Get or create the global database factory instance.

    Args:
        db_path: Path to SQLite database (only used for SQLite)

    Returns:
        DatabaseFactory instance
    """
    global _db_factory
    if _db_factory is None:
        _db_factory = DatabaseFactory(db_path=db_path)
    return _db_factory

def set_db_factory(factory: DatabaseFactory):
"""Set the global database factory instance (for testing)."""
global \_db_factory
\_db_factory = factory

## FILE: backend/core/kernel.py

# backend/core/kernel.py

import logging
import importlib
from typing import Dict, Optional
from pydantic import ValidationError
from backend.core.models import AgentInput, AgentOutput
from backend.core.registry import AgentRegistry
from backend.core.schemas import TASK_SCHEMA_MAP
from backend.core.memory import memory

class Kernel:
def **init**(self):
self.logger = logging.getLogger("ApexKernel")
self.agents: Dict[str, any] = {}

        # Dynamic Registration from Registry
        self.logger.info("⚡ Booting Apex Sovereign OS...")
        self._boot_agents()

    def _boot_agents(self):
        """Dynamically loads all agents defined in the Registry."""
        for key, (module_path, class_name) in AgentRegistry.DIRECTORY.items():
            self.register_agent(key, module_path, class_name)

    def register_agent(self, key: str, module_path: str, class_name: str):
        """
        Register an agent with validation and error handling.

        Validates:
        - Module path is whitelisted (backend.modules.*)
        - Class exists and inherits from BaseAgent
        - Agent can be instantiated
        """
        try:
            # Validate module path for security
            if not isinstance(module_path, str) or not module_path:
                raise ValueError(f"Invalid module_path for agent {key}: must be non-empty string")

            # Whitelist module paths (security: prevent importing dangerous modules)
            if not module_path.startswith("backend.modules."):
                raise ValueError(f"Module path must start with 'backend.modules.': {module_path}")

            # Validate key format
            if not isinstance(key, str) or not key:
                raise ValueError(f"Invalid agent key: must be non-empty string")
            if not key.replace("_", "").replace("-", "").isalnum():
                raise ValueError(f"Invalid agent key format (alphanumeric, _, - only): {key}")

            # Validate class name
            if not isinstance(class_name, str) or not class_name:
                raise ValueError(f"Invalid class_name for agent {key}: must be non-empty string")

            # Import module
            try:
                module = importlib.import_module(module_path)
            except ModuleNotFoundError as e:
                self.logger.error(f"❌ Module NOT FOUND for {key} at {module_path}: {e}")
                return  # Skip this agent, continue booting
            except ImportError as e:
                self.logger.error(f"❌ Import error for {key} at {module_path}: {e}")
                return  # Skip this agent

            # Get agent class
            try:
                agent_class = getattr(module, class_name)
            except AttributeError as e:
                self.logger.error(f"❌ Class {class_name} NOT FOUND in {module_path}: {e}")
                return  # Skip this agent

            # Validate agent class inherits from BaseAgent
            from backend.core.agent_base import BaseAgent
            if not issubclass(agent_class, BaseAgent):
                self.logger.error(f"❌ Class {class_name} must inherit from BaseAgent")
                return  # Skip this agent

            # Validate agent has required _execute method
            if not hasattr(agent_class, '_execute'):
                self.logger.error(f"❌ Class {class_name} missing required _execute method")
                return  # Skip this agent

            # Instantiate agent
            try:
                agent_instance = agent_class()
                self.agents[key] = agent_instance
                self.logger.info(f"✅ Registered Agent: {key} ({module_path}.{class_name})")
            except Exception as e:
                self.logger.error(f"❌ Failed to instantiate agent {key}: {e}", exc_info=True)
                return  # Skip this agent

        except ValueError as e:
            self.logger.error(f"❌ Validation error for agent {key}: {e}")
        except Exception as e:
            self.logger.error(f"❌ Unexpected error loading agent {key}: {e}", exc_info=True)

    def _resolve_agent(self, task: str) -> Optional[str]:
        """
        Smart Routing: Maps a task name to a registered agent key.
        Priority 1: Exact Match (e.g. task='onboarding' -> agent='onboarding')
        Priority 2: Prefix Match (e.g. task='onboarding_start' -> agent='onboarding')

        Uses strict prefix matching to avoid collisions.
        """
        if not task or not isinstance(task, str):
            self.logger.warning(f"Invalid task name: {task}")
            return None

        # Validate task format (security: prevent injection)
        if len(task) > 100:  # Reasonable length limit
            self.logger.warning(f"Task name too long: {len(task)} chars")
            return None

        self.logger.debug(f"Resolving agent for task: {task}")

        # 1. Exact Match (highest priority)
        if task in self.agents:
            self.logger.debug(f"Exact match found: {task}")
            return task

        # 2. Prefix Match (strict: task must start with agent_key + "_")
        # This prevents collisions like "write" matching "rewrite_pages"
        for agent_key in sorted(self.agents.keys(), key=len, reverse=True):  # Longest first
            if task.startswith(agent_key + "_"):
                self.logger.debug(f"Prefix match found: {agent_key} for task {task}")
                return agent_key

        self.logger.debug(f"No agent match found for task: {task}")
        return None

    async def dispatch(self, packet: AgentInput) -> AgentOutput:
        """
        The Kernel's dispatch method - the central routing hub.

        Data Flow:
        1. Receives AgentInput packet from /api/run endpoint (main.py)
        2. Validates task and resolves agent via Registry
        3. Checks if system agent (bypasses DNA loading)
        4. For regular agents: Loads DNA config and verifies project ownership
        5. Injects config into agent instance
        6. Executes agent.run() which calls agent._execute()
        7. Returns AgentOutput back to /api/run endpoint

        This is the "brain" that connects the frontend request to the correct agent.
        """
        try:
            # Validate input packet
            if not packet or not hasattr(packet, 'task'):
                self.logger.error("Invalid AgentInput packet received")
                return AgentOutput(
                    status="error",
                    message="Invalid request packet."
                )

            # Validate task name
            if not packet.task or not isinstance(packet.task, str):
                self.logger.error(f"Invalid task name: {packet.task}")
                return AgentOutput(
                    status="error",
                    message="Invalid task name provided."
                )

            # Validate user_id
            if not packet.user_id or not isinstance(packet.user_id, str):
                self.logger.error(f"Invalid user_id: {packet.user_id}")
                return AgentOutput(
                    status="error",
                    message="Invalid user identifier."
                )

            self.logger.info(f"📡 Dispatching Task: {packet.task} | User: {packet.user_id}")

            # --- 1. RESOLVE AGENT ---
            agent_key = self._resolve_agent(packet.task)

            if not agent_key:
                self.logger.error(f"⛔ No agent found for task: {packet.task}")
                return AgentOutput(
                    status="error",
                    message=f"System could not resolve an agent for task '{packet.task}'. Check Registry."
                )

            # Validate agent exists in registry (double-check)
            if agent_key not in self.agents:
                self.logger.error(f"⛔ Agent {agent_key} not found in loaded agents (registration may have failed)")
                return AgentOutput(
                    status="error",
                    message=f"Agent '{agent_key}' is not available. Registration may have failed."
                )

            # --- 1b. VALIDATE PARAMS (strict Pydantic) ---
            schema_class = TASK_SCHEMA_MAP.get(agent_key)
            if schema_class is not None:
                try:
                    schema_class.model_validate(packet.params or {})
                except ValidationError as e:
                    self.logger.warning(f"Params validation failed for task {packet.task}: {e}")
                    raise

            # --- 2. BYPASS RULE: System Agents (No DNA Needed) ---
            # System agents bypass config loading because they don't need project context.
            # - onboarding: Creates the DNA config
            # - health_check: System-wide health monitoring (no project needed)
            # - cleanup: System-wide maintenance (no project needed)
            # - log_usage: System-wide usage tracking (uses hardcoded pricing, no config needed, but needs project_id/user_id)
            system_agents = ["onboarding", "health_check", "cleanup", "log_usage"]
            # System agents that need context injection (project_id/user_id) but not DNA config
            system_agents_with_context = ["log_usage"]

            if agent_key in system_agents:
                self.logger.debug(f"System agent detected: {agent_key} - bypassing DNA loading")

                # Some system agents still need project_id/user_id injected (but not DNA config)
                if agent_key in system_agents_with_context:
                    # Extract project_id from params
                    niche = None
                    if packet.params:
                        niche = packet.params.get("niche") or packet.params.get("project_id")

                    if not niche:
                        self.logger.error(f"No project_id specified for system agent {agent_key}")
                        return AgentOutput(
                            status="error",
                            message="No project_id specified. Please provide a valid project_id in params."
                        )

                    # Validate project_id format
                    if not isinstance(niche, str) or not niche:
                        self.logger.error(f"Invalid project_id format: {niche}")
                        return AgentOutput(
                            status="error",
                            message="Invalid project identifier format."
                        )

                    import re
                    if not re.match(r'^[a-zA-Z0-9_-]+$', niche):
                        self.logger.error(f"Project_id contains invalid characters: {niche}")
                        return AgentOutput(
                            status="error",
                            message="Invalid project identifier format. Only alphanumeric characters, underscores, and hyphens allowed."
                        )

                    # Verify project ownership
                    try:
                        if not memory.verify_project_ownership(packet.user_id, niche):
                            self.logger.error(f"Project ownership verification failed: user={packet.user_id}, project={niche}")
                            return AgentOutput(
                                status="error",
                                message=f"Project '{niche}' not found or access denied."
                            )
                    except Exception as e:
                        self.logger.error(f"Project ownership verification error: {e}", exc_info=True)
                        return AgentOutput(
                            status="error",
                            message="Failed to verify project ownership."
                        )

                    # Inject context (but not config - system agents don't need DNA)
                    agent = self.agents[agent_key]
                    agent.project_id = niche
                    agent.user_id = packet.user_id
                    agent.config = {}  # Empty config for system agents
                    self.logger.debug(f"Injected context for system agent {agent_key}: project={niche}, user={packet.user_id}")

                try:
                    return await self.agents[agent_key].run(packet)
                except Exception as e:
                    self.logger.error(f"System agent {agent_key} execution failed: {e}", exc_info=True)
                    return AgentOutput(
                        status="error",
                        message=f"System agent '{agent_key}' execution failed: {str(e)}"
                    )

            # --- 3. SMART CONTEXT LOADING (DNA) ---
            # Regular agents need project context (DNA config)
            # Detect Project ID from Params OR Memory
            niche = None
            if packet.params:
                niche = packet.params.get("niche") or packet.params.get("project_id")

            if not niche and packet.user_id:
                # Auto-lookup active project
                try:
                    project = memory.get_user_project(packet.user_id)
                    if project:
                        niche = project.get('project_id')
                        if niche:
                            self.logger.info(f"🔍 Context Loaded from memory: {niche}")
                except Exception as e:
                    self.logger.error(f"Failed to load user project for {packet.user_id}: {e}", exc_info=True)
                    return AgentOutput(
                        status="error",
                        message=f"Failed to load user project: {str(e)}"
                    )

            if not niche:
                # Fail explicitly - no project_id and no auto-lookup
                self.logger.error(f"No niche/project_id specified for user {packet.user_id}")
                return AgentOutput(
                    status="error",
                    message="No project_id specified. Please provide a valid project_id in params or create a project first."
                )

            # Validate project_id format (security: prevent path traversal)
            if not isinstance(niche, str) or not niche:
                self.logger.error(f"Invalid project_id format: {niche}")
                return AgentOutput(
                    status="error",
                    message="Invalid project identifier format."
                )

            import re
            if not re.match(r'^[a-zA-Z0-9_-]+$', niche):
                self.logger.error(f"Project_id contains invalid characters: {niche}")
                return AgentOutput(
                    status="error",
                    message="Invalid project identifier format. Only alphanumeric characters, underscores, and hyphens allowed."
                )

            # CRITICAL: Verify project ownership before loading config
            try:
                if not memory.verify_project_ownership(packet.user_id, niche):
                    self.logger.error(f"Project ownership verification failed: user={packet.user_id}, project={niche}")
                    return AgentOutput(
                        status="error",
                        message=f"Project '{niche}' not found or access denied."
                    )
            except Exception as e:
                self.logger.error(f"Project ownership verification error: {e}", exc_info=True)
                return AgentOutput(
                    status="error",
                    message="Failed to verify project ownership."
                )

            # Extract campaign_id from params if present
            campaign_id = packet.params.get("campaign_id")

            # Load DNA Profile (and campaign config if campaign_id provided)
            from backend.core.config import ConfigLoader
            try:
                config_loader = ConfigLoader()
                user_config = config_loader.load(niche, campaign_id=campaign_id)

                # Check for config errors
                if not isinstance(user_config, dict):
                    self.logger.error(f"Config loader returned non-dict for {niche}")
                    return AgentOutput(
                        status="error",
                        message=f"Invalid configuration format for project '{niche}'."
                    )

                if "error" in user_config:
                    error_msg = user_config.get("error", "Unknown config error")
                    self.logger.error(f"Config loading failed for {niche}: {error_msg}")
                    return AgentOutput(
                        status="error",
                        message=f"Configuration error for project '{niche}': {error_msg}"
                    )
            except Exception as e:
                self.logger.error(f"Failed to load config for {niche}: {e}", exc_info=True)
                return AgentOutput(
                    status="error",
                    message=f"Failed to load configuration for project '{niche}': {str(e)}"
                )

            # Inject Context into Agent (Titanium Standard)
            agent = self.agents[agent_key]
            agent.config = user_config
            agent.project_id = niche
            agent.user_id = packet.user_id
            agent.campaign_id = campaign_id  # Inject campaign_id if present

            # Validate injected context
            if not agent.config or not isinstance(agent.config, dict):
                self.logger.error(f"Failed to inject valid config for agent {agent_key}")
                return AgentOutput(
                    status="error",
                    message="Configuration injection failed."
                )

            self.logger.debug(f"Injected context for {agent_key}: project={niche}, user={packet.user_id}")

            # --- 4. EXECUTE ---
            try:
                return await agent.run(packet)
            except Exception as e:
                self.logger.error(f"Agent {agent_key} execution failed: {e}", exc_info=True)
                return AgentOutput(
                    status="error",
                    message=f"Agent '{agent_key}' execution failed: {str(e)}"
                )

        except Exception as e:
            self.logger.error(f"Unexpected error in kernel dispatch: {e}", exc_info=True)
            return AgentOutput(
                status="error",
                message="Internal system error during dispatch. Please try again."
            )

# Singleton Kernel

kernel = Kernel()

## FILE: backend/core/logger.py

# backend/core/logger.py

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

# ANSI color codes for terminal output

class ColoredFormatter(logging.Formatter):
"""Custom formatter with ANSI color codes for console output."""

    # Color codes
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

    COLORS = {
        'INFO': GREEN,
        'WARNING': YELLOW,
        'ERROR': RED,
        'CRITICAL': RED,
        'DEBUG': BLUE,
    }

    def format(self, record):
        # Store original levelname
        original_levelname = record.levelname

        # Get the color for this log level
        color = self.COLORS.get(record.levelname, '')
        reset = self.RESET

        # Temporarily modify levelname for formatting
        record.levelname = f"{color}{original_levelname}{reset}"

        # Format the message
        formatted = super().format(record)

        # Restore original levelname (just in case)
        record.levelname = original_levelname

        return formatted

def setup_logging():
"""
Configure centralized logging for the Apex backend.

    Sets up:
    - Color-coded console output (Green INFO, Yellow WARNING, Red ERROR)
    - Rotating file handler (logs/apex.log, 10MB max, 5 backups)
    - Format: [YYYY-MM-DD HH:MM:SS] [LEVEL] [COMPONENT] : Message
    """
    # Create logs directory if it doesn't exist
    logs_dir = "logs"
    os.makedirs(logs_dir, exist_ok=True)

    # Define log format
    log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] : %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Console Handler with colors
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = ColoredFormatter(log_format, datefmt=date_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File Handler with rotation
    log_file_path = os.path.join(logs_dir, "apex.log")
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    # File formatter without ANSI codes
    file_formatter = logging.Formatter(log_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Return the root logger
    logger = logging.getLogger("Apex")
    logger.info("Logging system initialized - Console: colored | File: logs/apex.log")
    return logger

## FILE: backend/core/memory.py

# backend/core/memory.py

import chromadb
import uuid
import json
import logging
import os
import hashlib
import secrets
from datetime import datetime
from typing import List, Dict, Any, Optional
from google import genai # <--- REQUIRED
from backend.core.models import Entity
from backend.core.security import security_core
from backend.core.db import get_db_factory, DatabaseError

# --- Google Embedding Wrapper using LLM Gateway ---

class GoogleEmbeddingFunction:
"""
ChromaDB-compatible embedding function using Google Gemini API via LLMGateway.
Ensures consistent embedding generation across the system.
"""
def **init**(self): # Import here to avoid circular dependency
from backend.core.services.llm_gateway import llm_gateway
self.llm_gateway = llm_gateway # ChromaDB requires a 'name' attribute for embedding functions
self.name = "google_embedding_function"
self.model = "text-embedding-004"

    def __call__(self, input: List[str]) -> List[List[float]]:
        """
        Generate embeddings for input texts using Google Gemini API.

        Args:
            input: List of text strings to embed

        Returns:
            List of embedding vectors (list of floats)
        """
        if not input:
            return []

        try:
            # Use LLM Gateway for consistent embedding generation
            return self.llm_gateway.generate_embeddings(
                texts=input,
                model=self.model
            )
        except Exception as e:
            logging.getLogger("ApexMemory").error(f"Failed to generate embeddings: {e}", exc_info=True)
            raise

    def embed_query(self, input: str) -> List[float]:
        """
        Generate embedding for a single query string.
        Required by ChromaDB for query operations.

        Args:
            input: Single query string to embed (ChromaDB passes this as keyword arg)

        Returns:
            Embedding vector (list of floats)
        """
        if not input:
            return []

        try:
            embeddings = self.__call__([input])
            return embeddings[0] if embeddings else []
        except Exception as e:
            logging.getLogger("ApexMemory").error(f"Failed to generate query embedding: {e}", exc_info=True)
            raise

class MemoryManager:
def **init**(self, db_path="data/apex.db", vector_path="data/chroma_db"):
self.logger = logging.getLogger("ApexMemory")

        # Convert to absolute paths to avoid path-related issues
        self.db_path = os.path.abspath(db_path)
        self.vector_path = os.path.abspath(vector_path)

        # Ensure directories exist with proper permissions (only for SQLite)
        if not os.getenv("DATABASE_URL"):
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.vector_path, exist_ok=True)

        # Initialize database factory
        self.db_factory = get_db_factory(db_path=self.db_path)

        self._init_database()

        # Initialize Vector DB with error handling
        try:
            self.chroma_client = chromadb.PersistentClient(path=self.vector_path)

            # Create and store embedding function instance (uses Google Gemini API)
            # We'll manually use this for all operations to ensure Google embeddings
            self.embedding_fn = GoogleEmbeddingFunction()

            # Try to get existing collection first
            try:
                # get_collection() uses the stored embedding function from when collection was created
                # Don't pass embedding_function - ChromaDB doesn't accept it for get_collection()
                self.vector_collection = self.chroma_client.get_collection(
                    name="apex_context"
                )
                # Manually set our embedding function to ensure we use Google embeddings
                # This overrides whatever ChromaDB stored
                try:
                    self.vector_collection._embedding_function = self.embedding_fn
                except Exception:
                    # If we can't set it directly, we'll manually embed in query/save methods
                    pass
                self.logger.info("Loaded existing ChromaDB collection (using Google embeddings)")
            except Exception as get_error:
                # Collection doesn't exist, create it with Google embedding function
                try:
                    self.vector_collection = self.chroma_client.create_collection(
                        name="apex_context",
                        embedding_function=self.embedding_fn
                    )
                    self.logger.info("Created new ChromaDB collection with Google embeddings")
                except Exception as create_error:
                    # Collection might have been created between get and create
                    error_msg = str(create_error).lower()
                    if "already exists" in error_msg or "duplicate" in error_msg:
                        # Collection exists, get it and set our embedding function
                        self.vector_collection = self.chroma_client.get_collection(
                            name="apex_context"
                        )
                        try:
                            self.vector_collection._embedding_function = self.embedding_fn
                        except Exception:
                            pass
                        self.logger.info("Loaded existing ChromaDB collection (recovered from race condition)")
                    else:
                        # Re-raise if it's a different error
                        raise create_error

            self.chroma_enabled = True
            self.logger.info("🧠 Memory Systems Online (SQL + Google RAG)")
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize ChromaDB: {e}")
            self.logger.warning("⚠️ Continuing without vector memory (RAG disabled)")
            self.chroma_client = None
            self.vector_collection = None
            self.chroma_enabled = False
            self.logger.info("🧠 Memory Systems Online (SQL only)")

    def _init_database(self):
        """Creates tables with Market-Ready schema (database-agnostic)."""
        json_type = self.db_factory.get_json_type()
        placeholder = self.db_factory.get_placeholder()

        with self.db_factory.get_cursor() as cursor:
            # 1. USERS (With Hashed Passwords)
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL
                )
            ''')

            # 2. PROJECTS
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    niche TEXT,
                    dna_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            ''')

            # 3. ENTITIES
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    project_id TEXT,
                    entity_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    primary_contact TEXT,
                    metadata {json_type},
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_tenant ON entities(tenant_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_project ON entities(project_id)")

            # 4. CAMPAIGNS
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    module TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'DRAFT',
                    config {json_type} NOT NULL,
                    stats {json_type},
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                )
            ''')

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_campaigns_project ON campaigns(project_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_campaigns_module ON campaigns(module)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status)")

            # 5. SECRETS
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS client_secrets (
                    user_id TEXT PRIMARY KEY,
                    wp_url TEXT,
                    wp_user TEXT,
                    wp_auth_hash TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            ''')

    # ====================================================
    # SECTION A: SECURITY & AUTH
    # ====================================================
    def _hash_password(self, password: str, salt: Optional[str] = None) -> (str, str):
        if not salt:
            salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
        return pwd_hash, salt

    def create_user(self, email, password):
        self.logger.debug(f"Creating user {email}")
        try:
            pwd_hash, salt = self._hash_password(password)
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(
                    f"INSERT INTO users (user_id, password_hash, salt) VALUES ({placeholder}, {placeholder}, {placeholder})",
                    (email, pwd_hash, salt)
                )
            self.logger.info(f"Successfully created user {email}")
            return True
        except DatabaseError as e:
            # Check if it's an integrity error (duplicate key)
            error_str = str(e).lower()
            if "unique" in error_str or "duplicate" in error_str or "already exists" in error_str:
                self.logger.warning(f"User {email} already exists: {e}")
                return False
            self.logger.error(f"Database error creating user {email}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error creating user {email}: {e}")
            return False

    def _user_exists(self, user_id: str) -> bool:
        """Check if user exists (for JWT validation)."""
        try:
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor(commit=False) as cursor:
                cursor.execute(f"SELECT 1 FROM users WHERE user_id = {placeholder}", (user_id,))
                exists = cursor.fetchone() is not None
                return exists
        except DatabaseError as e:
            self.logger.error(f"Database error checking user existence for {user_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error checking user existence for {user_id}: {e}")
            return False

    def verify_user(self, email, password):
        self.logger.debug(f"Verifying user credentials for {email}")
        try:
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor(commit=False) as cursor:
                cursor.execute(f"SELECT password_hash, salt FROM users WHERE user_id = {placeholder}", (email,))
                row = cursor.fetchone()

                if row:
                    stored_hash, salt = row[0], row[1]
                    check_hash, _ = self._hash_password(password, salt)
                    is_valid = check_hash == stored_hash
                    if is_valid:
                        self.logger.debug(f"Credentials verified for user {email}")
                    else:
                        self.logger.debug(f"Invalid credentials for user {email}")
                    return is_valid
                self.logger.debug(f"User {email} not found")
                return False
        except DatabaseError as e:
            self.logger.error(f"Database error verifying user {email}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error verifying user {email}: {e}")
            return False

    # ====================================================
    # SECTION B: PROJECT MANAGEMENT
    # ====================================================
    def register_project(self, user_id, project_id, niche):
        self.logger.debug(f"Registering project {project_id} for user {user_id}")
        try:
            path = f"data/profiles/{project_id}/dna.generated.yaml"
            sql = self.db_factory.get_insert_or_replace_sql(
                table="projects",
                columns=["project_id", "user_id", "niche", "dna_path"],
                primary_key="project_id"
            )
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(sql, (project_id, user_id, niche, path))
            self.logger.info(f"Successfully registered project {project_id} for user {user_id}")
        except DatabaseError as e:
            self.logger.error(f"Database error registering project {project_id} for user {user_id}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error registering project {project_id} for user {user_id}: {e}")
            raise

    def get_user_project(self, user_id):
        self.logger.debug(f"Fetching user project for user {user_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            conn = self.db_factory.get_connection()
            self.db_factory.set_row_factory(conn)
            try:
                cursor = self.db_factory.get_cursor_with_row_factory(conn)
                cursor.execute(f"SELECT * FROM projects WHERE user_id = {placeholder} ORDER BY created_at DESC LIMIT 1", (user_id,))
                row = cursor.fetchone()
                result = dict(row) if row else None
                if result:
                    self.logger.debug(f"Found project {result.get('project_id')} for user {user_id}")
                else:
                    self.logger.debug(f"No project found for user {user_id}")
                return result
            finally:
                cursor.close()
                conn.close()
        except DatabaseError as e:
            self.logger.error(f"Database error fetching user project for user {user_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error fetching user project for user {user_id}: {e}")
            return None

    def get_projects(self, user_id: str) -> List[Dict]:
        """Get all projects for a specific user."""
        self.logger.debug(f"Fetching all projects for user {user_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            conn = self.db_factory.get_connection()
            self.db_factory.set_row_factory(conn)
            try:
                cursor = self.db_factory.get_cursor_with_row_factory(conn)
                cursor.execute(f"SELECT * FROM projects WHERE user_id = {placeholder} ORDER BY created_at DESC", (user_id,))
                rows = cursor.fetchall()
                results = [dict(row) for row in rows]
                self.logger.debug(f"Found {len(results)} projects for user {user_id}")
                return results
            finally:
                cursor.close()
                conn.close()
        except DatabaseError as e:
            self.logger.error(f"Database error fetching projects for user {user_id}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching projects for user {user_id}: {e}")
            return []

    def verify_project_ownership(self, user_id: str, project_id: str) -> bool:
        """
        Verify that a project belongs to a specific user.

        Critical for multi-tenant security.
        Future: With Supabase RLS, this check happens at database level.
        """
        self.logger.debug(f"Verifying project ownership: user={user_id}, project={project_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor(commit=False) as cursor:
                cursor.execute(
                    f"SELECT 1 FROM projects WHERE project_id = {placeholder} AND user_id = {placeholder}",
                    (project_id, user_id)
                )
                exists = cursor.fetchone() is not None
                if not exists:
                    self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
                return exists
        except DatabaseError as e:
            self.logger.error(f"Database error verifying project ownership: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error verifying project ownership: {e}")
            return False

    def get_project_owner(self, project_id: str) -> Optional[str]:
        """
        Get the user_id (owner) of a project.

        Used to find the correct tenant_id for operations.
        Returns None if project doesn't exist.
        """
        self.logger.debug(f"Getting project owner for project {project_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor(commit=False) as cursor:
                cursor.execute(f"SELECT user_id FROM projects WHERE project_id = {placeholder}", (project_id,))
                row = cursor.fetchone()

                if row:
                    user_id = row[0]
                    self.logger.debug(f"Found project owner: {user_id} for project {project_id}")
                    return user_id
                else:
                    self.logger.warning(f"Project {project_id} not found in database")
                    return None
        except DatabaseError as e:
            self.logger.error(f"Database error getting project owner for {project_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting project owner for {project_id}: {e}")
            return None

    # ====================================================
    # SECTION B.5: CAMPAIGN MANAGEMENT
    # ====================================================
    def create_campaign(self, user_id: str, project_id: str, name: str, module: str, config: Dict[str, Any]) -> str:
        """
        Create a new campaign for a project.
        Returns campaign_id (UUID format: cmp_xxxxx).
        """
        self.logger.debug(f"Creating campaign for project {project_id}, module {module}")
        try:
            # Verify project ownership
            if not self.verify_project_ownership(user_id, project_id):
                raise ValueError(f"User {user_id} does not own project {project_id}")

            # Generate campaign_id (format: cmp_xxxxx)
            import uuid
            campaign_id = f"cmp_{uuid.uuid4().hex[:10]}"

            # Insert campaign
            json_type = self.db_factory.get_json_type()
            placeholder = self.db_factory.get_placeholder()

            with self.db_factory.get_cursor() as cursor:
                cursor.execute(f'''
                    INSERT INTO campaigns (id, project_id, name, module, status, config, stats)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                ''', (
                    campaign_id,
                    project_id,
                    name,
                    module,
                    'DRAFT',
                    json.dumps(config),
                    json.dumps({})
                ))

            self.logger.info(f"Successfully created campaign {campaign_id} for project {project_id}")
            return campaign_id
        except DatabaseError as e:
            self.logger.error(f"Database error creating campaign: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error creating campaign: {e}")
            raise

    def get_campaign(self, campaign_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a campaign by ID with RLS check (via project ownership).
        Returns None if not found or access denied.
        """
        self.logger.debug(f"Fetching campaign {campaign_id} for user {user_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            conn = self.db_factory.get_connection()
            self.db_factory.set_row_factory(conn)
            try:
                cursor = self.db_factory.get_cursor_with_row_factory(conn)
                # Join with projects to verify ownership
                cursor.execute(f'''
                    SELECT c.*, p.user_id
                    FROM campaigns c
                    JOIN projects p ON c.project_id = p.project_id
                    WHERE c.id = {placeholder} AND p.user_id = {placeholder}
                ''', (campaign_id, user_id))
                row = cursor.fetchone()

                if row:
                    result = dict(row)
                    # Parse JSON fields
                    if result.get('config'):
                        result['config'] = json.loads(result['config']) if isinstance(result['config'], str) else result['config']
                    if result.get('stats'):
                        result['stats'] = json.loads(result['stats']) if isinstance(result['stats'], str) else result['stats']
                    # Remove user_id from result (it's from join)
                    result.pop('user_id', None)
                    self.logger.debug(f"Found campaign {campaign_id}")
                    return result
                else:
                    self.logger.debug(f"Campaign {campaign_id} not found or access denied")
                    return None
            finally:
                cursor.close()
                conn.close()
        except DatabaseError as e:
            self.logger.error(f"Database error fetching campaign {campaign_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error fetching campaign {campaign_id}: {e}")
            return None

    def get_campaigns_by_project(self, user_id: str, project_id: str, module: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all campaigns for a project, optionally filtered by module.
        Returns empty list if project not found or access denied.
        """
        self.logger.debug(f"Fetching campaigns for project {project_id}, module={module}")
        try:
            # Verify project ownership
            if not self.verify_project_ownership(user_id, project_id):
                self.logger.warning(f"Access denied: user {user_id} does not own project {project_id}")
                return []

            placeholder = self.db_factory.get_placeholder()
            conn = self.db_factory.get_connection()
            self.db_factory.set_row_factory(conn)
            try:
                cursor = self.db_factory.get_cursor_with_row_factory(conn)

                if module:
                    cursor.execute(f'''
                        SELECT * FROM campaigns
                        WHERE project_id = {placeholder} AND module = {placeholder}
                        ORDER BY created_at DESC
                    ''', (project_id, module))
                else:
                    cursor.execute(f'''
                        SELECT * FROM campaigns
                        WHERE project_id = {placeholder}
                        ORDER BY created_at DESC
                    ''', (project_id,))

                rows = cursor.fetchall()
                results = []
                for row in rows:
                    result = dict(row)
                    # Parse JSON fields
                    if result.get('config'):
                        result['config'] = json.loads(result['config']) if isinstance(result['config'], str) else result['config']
                    if result.get('stats'):
                        result['stats'] = json.loads(result['stats']) if isinstance(result['stats'], str) else result['stats']
                    results.append(result)

                self.logger.debug(f"Found {len(results)} campaigns for project {project_id}")
                return results
            finally:
                cursor.close()
                conn.close()
        except DatabaseError as e:
            self.logger.error(f"Database error fetching campaigns: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching campaigns: {e}")
            return []

    def update_campaign_status(self, campaign_id: str, user_id: str, status: str) -> bool:
        """
        Update campaign status. Validates ownership via project.
        Returns True on success, False on failure.
        """
        self.logger.debug(f"Updating campaign {campaign_id} status to {status}")
        try:
            # Verify ownership by checking if campaign exists and user owns the project
            campaign = self.get_campaign(campaign_id, user_id)
            if not campaign:
                self.logger.warning(f"Cannot update campaign {campaign_id}: not found or access denied")
                return False

            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(f'''
                    UPDATE campaigns
                    SET status = {placeholder}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = {placeholder}
                ''', (status, campaign_id))

            self.logger.info(f"Successfully updated campaign {campaign_id} status to {status}")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error updating campaign status: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating campaign status: {e}")
            return False

    def update_campaign_stats(self, campaign_id: str, user_id: str, stats: Dict[str, Any]) -> bool:
        """
        Update campaign stats. Validates ownership via project.
        Merges with existing stats (doesn't overwrite).
        Returns True on success, False on failure.
        """
        self.logger.debug(f"Updating campaign {campaign_id} stats")
        try:
            # Verify ownership
            campaign = self.get_campaign(campaign_id, user_id)
            if not campaign:
                self.logger.warning(f"Cannot update campaign {campaign_id}: not found or access denied")
                return False

            # Merge with existing stats
            existing_stats = campaign.get('stats', {}) or {}
            merged_stats = {**existing_stats, **stats}

            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(f'''
                    UPDATE campaigns
                    SET stats = {placeholder}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = {placeholder}
                ''', (json.dumps(merged_stats), campaign_id))

            self.logger.info(f"Successfully updated campaign {campaign_id} stats")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error updating campaign stats: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating campaign stats: {e}")
            return False

    def update_campaign_config(self, campaign_id: str, user_id: str, new_config: Dict[str, Any]) -> bool:
        """
        Update campaign config. Validates ownership via project.

        Overwrites the existing config with the provided dictionary.
        """
        self.logger.debug(f"Updating campaign {campaign_id} config")
        try:
            # Verify ownership
            campaign = self.get_campaign(campaign_id, user_id)
            if not campaign:
                self.logger.warning(f"Cannot update campaign {campaign_id}: not found or access denied")
                return False

            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE campaigns
                    SET config = {placeholder}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = {placeholder}
                    """,
                    (json.dumps(new_config), campaign_id),
                )

            self.logger.info(f"Successfully updated campaign {campaign_id} config")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error updating campaign config: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating campaign config: {e}")
            return False

    # ====================================================
    # SECTION C: SCALABLE ENTITY STORAGE
    # ====================================================
    def save_entity(self, entity: Entity, project_id: Optional[str] = None) -> bool:
        """
        Saves an entity to the database.

        Priority for project_id:
        1. Explicit parameter (project_id argument)
        2. Entity.project_id attribute (if set by agent)
        3. Entity.metadata.get("project_id") (fallback for legacy data)
        """
        self.logger.debug(f"Saving entity {entity.id} of type {entity.entity_type} for tenant {entity.tenant_id}")
        try:
            # Priority: parameter > entity attribute > metadata
            if project_id is None:
                # Check if entity has project_id attribute (set by agents)
                project_id = getattr(entity, 'project_id', None)
                if project_id is None:
                    # Fallback to metadata (for legacy data)
                    project_id = entity.metadata.get("project_id")

            sql = self.db_factory.get_insert_or_replace_sql(
                table="entities",
                columns=["id", "tenant_id", "project_id", "entity_type", "name", "primary_contact", "metadata", "created_at"],
                primary_key="id"
            )
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(sql, (
                    entity.id,
                    entity.tenant_id,
                    project_id,
                    entity.entity_type,
                    entity.name,
                    entity.primary_contact,
                    json.dumps(entity.metadata),
                    entity.created_at
                ))
            self.logger.info(f"Successfully saved entity {entity.id} of type {entity.entity_type}")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error saving entity {entity.id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error saving entity {entity.id}: {e}")
            return False

    def get_entities(self, tenant_id: str, entity_type: Optional[str] = None,
                     project_id: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict]:
        self.logger.debug(f"Fetching entities for tenant {tenant_id}, type: {entity_type}, project: {project_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            conn = self.db_factory.get_connection()
            self.db_factory.set_row_factory(conn)
            try:
                cursor = self.db_factory.get_cursor_with_row_factory(conn)

                query = f"SELECT * FROM entities WHERE tenant_id = {placeholder}"
                params = [tenant_id]

                if entity_type:
                    query += f" AND entity_type = {placeholder}"
                    params.append(entity_type)

                if project_id:
                    query += f" AND project_id = {placeholder}"
                    params.append(project_id)

                query += f" ORDER BY created_at DESC LIMIT {placeholder} OFFSET {placeholder}"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                results = []
                for row in rows:
                    item = dict(row)
                    try:
                        item['metadata'] = json.loads(item['metadata'])
                    except (json.JSONDecodeError, TypeError) as e:
                        self.logger.warning(f"Failed to parse metadata JSON for entity {item.get('id', 'unknown')}: {e}")
                        item['metadata'] = {}
                    results.append(item)

                self.logger.debug(f"Found {len(results)} entities for tenant {tenant_id}")
                return results
            finally:
                cursor.close()
                conn.close()
        except DatabaseError as e:
            self.logger.error(f"Database error fetching entities for tenant {tenant_id}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching entities for tenant {tenant_id}: {e}")
            return []

    def update_entity(self, entity_id: str, new_metadata: dict) -> bool:
        """Updates the metadata of an existing entity."""
        self.logger.debug(f"Updating entity {entity_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor() as cursor:
                # 1. Fetch existing metadata
                cursor.execute(f"SELECT metadata FROM entities WHERE id = {placeholder}", (entity_id,))
                row = cursor.fetchone()

                if not row:
                    self.logger.warning(f"Entity {entity_id} not found for update")
                    return False

                # 2. Merge new data with old data
                try:
                    current_meta = json.loads(row[0])
                except (json.JSONDecodeError, TypeError) as e:
                    self.logger.warning(f"Failed to parse existing metadata JSON for entity {entity_id}: {e}")
                    current_meta = {}
                current_meta.update(new_metadata)

                # 3. Save back
                cursor.execute(
                    f"UPDATE entities SET metadata = {placeholder} WHERE id = {placeholder}",
                    (json.dumps(current_meta), entity_id)
                )

            self.logger.info(f"Successfully updated entity {entity_id}")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error updating entity {entity_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating entity {entity_id}: {e}")
            return False

    def delete_entity(self, entity_id: str, tenant_id: str) -> bool:
        """Deletes an entity with RLS check."""
        self.logger.debug(f"Deleting entity {entity_id} for tenant {tenant_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor() as cursor:
                # Verify entity belongs to tenant (RLS)
                cursor.execute(f"SELECT id FROM entities WHERE id = {placeholder} AND tenant_id = {placeholder}", (entity_id, tenant_id))
                row = cursor.fetchone()

                if not row:
                    self.logger.warning(f"Entity {entity_id} not found or access denied for tenant {tenant_id}")
                    return False

                # Delete the entity
                cursor.execute(f"DELETE FROM entities WHERE id = {placeholder} AND tenant_id = {placeholder}", (entity_id, tenant_id))

            self.logger.info(f"Successfully deleted entity {entity_id} for tenant {tenant_id}")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error deleting entity {entity_id} for tenant {tenant_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error deleting entity {entity_id} for tenant {tenant_id}: {e}")
            return False

    def get_client_secrets(self, user_id: str) -> Optional[Dict[str, str]]:
        self.logger.debug(f"Fetching client secrets for user {user_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            conn = self.db_factory.get_connection()
            self.db_factory.set_row_factory(conn)
            try:
                cursor = self.db_factory.get_cursor_with_row_factory(conn)
                cursor.execute(f"SELECT wp_url, wp_user, wp_auth_hash FROM client_secrets WHERE user_id = {placeholder}", (user_id,))
                row = cursor.fetchone()

                if row:
                    self.logger.debug(f"Found client secrets for user {user_id}")
                    decrypted_password = None
                    if row["wp_auth_hash"]:
                        try:
                            decrypted_password = security_core.decrypt(row["wp_auth_hash"])
                        except Exception as e:
                            self.logger.error(f"Failed to decrypt wp_auth_hash for {user_id}: {e}")
                            decrypted_password = None

                    return {
                        "wp_url": row["wp_url"],
                        "wp_user": row["wp_user"],
                        "wp_password": decrypted_password
                    }
                self.logger.debug(f"No client secrets found for user {user_id}")
                return None
            finally:
                cursor.close()
                conn.close()
        except DatabaseError as e:
            self.logger.error(f"Database error retrieving client secrets for user {user_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error retrieving client secrets for user {user_id}: {e}")
            return None

    def save_client_secrets(self, user_id: str, wp_url: str, wp_user: str, wp_password: str) -> bool:
        """Save or update WordPress credentials for a user."""
        self.logger.debug(f"Saving client secrets for user {user_id}")
        try:
            try:
                encrypted_password = security_core.encrypt(wp_password)
            except Exception as e:
                self.logger.error(f"Encryption failed for wp_password for user {user_id}: {e}")
                return False

            sql = self.db_factory.get_insert_or_replace_sql(
                table="client_secrets",
                columns=["user_id", "wp_url", "wp_user", "wp_auth_hash"],
                primary_key="user_id"
            )
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(sql, (user_id, wp_url, wp_user, encrypted_password))

            self.logger.info(f"Successfully saved client secrets for user {user_id}")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error saving client secrets for user {user_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error saving client secrets for user {user_id}: {e}")
            return False

    # ====================================================
    # SECTION C.5: USAGE TRACKING & BILLING
    # ====================================================
    def create_usage_table_if_not_exists(self):
        """Creates the usage_ledger table if it doesn't exist."""
        try:
            with self.db_factory.get_cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS usage_ledger (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        resource_type TEXT NOT NULL,
                        quantity REAL NOT NULL,
                        cost_usd REAL NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Create index for faster monthly spend queries
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_project_timestamp ON usage_ledger(project_id, timestamp)")

            self.logger.debug("Usage ledger table ready")
        except DatabaseError as e:
            self.logger.error(f"Database error creating usage_ledger table: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error creating usage_ledger table: {e}")
            raise

    def log_usage(self, project_id: str, resource_type: str, quantity: float, cost_usd: float) -> bool:
        """
        Logs resource usage to the usage_ledger table.

        Args:
            project_id: Project identifier
            resource_type: Type of resource (e.g., "twilio_voice", "gemini_token")
            quantity: Quantity used (e.g., minutes, tokens)
            cost_usd: Cost in USD

        Returns:
            True on success, False on error
        """
        self.logger.debug(f"Logging usage: {resource_type} x {quantity} = ${cost_usd:.4f} for project {project_id}")
        try:
            # Ensure table exists
            self.create_usage_table_if_not_exists()

            # Generate ID
            usage_id = str(uuid.uuid4())
            placeholder = self.db_factory.get_placeholder()

            with self.db_factory.get_cursor() as cursor:
                cursor.execute(f'''
                    INSERT INTO usage_ledger (id, project_id, resource_type, quantity, cost_usd, timestamp)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                ''', (usage_id, project_id, resource_type, quantity, cost_usd, datetime.now()))

            self.logger.debug(f"Successfully logged usage record {usage_id}")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error logging usage for project {project_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error logging usage for project {project_id}: {e}")
            return False

    def get_monthly_spend(self, project_id: str) -> float:
        """
        Gets the total monthly spend for a project (current month).

        Args:
            project_id: Project identifier

        Returns:
            Total spend in USD for the current month (0.0 if no records)
        """
        self.logger.debug(f"Getting monthly spend for project {project_id}")
        try:
            # Ensure table exists
            self.create_usage_table_if_not_exists()

            placeholder = self.db_factory.get_placeholder()
            date_expr = self.db_factory.get_date_start_of_month()

            with self.db_factory.get_cursor(commit=False) as cursor:
                # Query for current month's spend
                cursor.execute(f'''
                    SELECT SUM(cost_usd)
                    FROM usage_ledger
                    WHERE project_id = {placeholder}
                    AND timestamp >= {date_expr}
                ''', (project_id,))

                row = cursor.fetchone()
                total_spend = float(row[0]) if row and row[0] is not None else 0.0

            self.logger.debug(f"Monthly spend for project {project_id}: ${total_spend:.2f}")
            return total_spend
        except DatabaseError as e:
            self.logger.error(f"Database error getting monthly spend for project {project_id}: {e}")
            return 0.0
        except Exception as e:
            self.logger.error(f"Unexpected error getting monthly spend for project {project_id}: {e}")
            return 0.0

    # ====================================================
    # SECTION D: SEMANTIC MEMORY (RAG)
    # ====================================================
    def save_context(self, tenant_id: str, text: str, metadata: Dict = {}, project_id: str = None, campaign_id: str = None):
        """Saves embeddings with Project and Campaign Context."""
        if not self.chroma_enabled or not self.vector_collection:
            self.logger.debug("ChromaDB not available, skipping context save")
            return

        try:
            metadata['tenant_id'] = tenant_id
            if project_id:
                metadata['project_id'] = project_id
            if campaign_id:
                metadata['campaign_id'] = campaign_id

            # Manually embed using our Google embedding function to ensure consistency
            embeddings = self.embedding_fn([text])

            self.vector_collection.add(
                documents=[text],
                embeddings=embeddings,  # Pass pre-embedded vectors
                metadatas=[metadata],
                ids=[str(uuid.uuid4())]
            )
        except Exception as e:
            self.logger.warning(f"Failed to save context to ChromaDB: {e}")

    def query_context(self, tenant_id: str, query: str, n_results: int = 3, project_id: str = None, campaign_id: str = None, return_metadata: bool = False):
        """Retrieves embeddings filtered by Project and Campaign.

        Args:
            tenant_id: User ID for RLS
            query: Search query text
            n_results: Number of results to return
            project_id: Optional project filter
            campaign_id: Optional campaign filter
            return_metadata: If True, returns list of dicts with 'text' and 'metadata'. If False, returns list of text strings.

        Returns:
            List of text strings (if return_metadata=False) or list of dicts with 'text' and 'metadata' (if return_metadata=True)
        """
        if not self.chroma_enabled or not self.vector_collection:
            self.logger.debug("ChromaDB not available, returning empty results")
            return []

        try:
            # Build where clause with tenant_id, project_id, and campaign_id filters
            where_conditions = [{"tenant_id": tenant_id}]

            if project_id:
                where_conditions.append({"project_id": project_id})

            if campaign_id:
                where_conditions.append({"campaign_id": campaign_id})

            if len(where_conditions) > 1:
                where_clause = {"$and": where_conditions}
            else:
                where_clause = where_conditions[0]

            # Manually embed query using our Google embedding function to ensure consistency
            query_embedding = self.embedding_fn.embed_query(query)

            results = self.vector_collection.query(
                query_embeddings=[query_embedding],  # Use pre-embedded vector instead of query_texts
                n_results=n_results,
                where=where_clause
            )

            if return_metadata:
                # Return list of dicts with text and metadata
                documents = results.get('documents', [[]])[0] if results.get('documents') else []
                metadatas = results.get('metadatas', [[]])[0] if results.get('metadatas') else []
                return [
                    {"text": doc, "metadata": meta}
                    for doc, meta in zip(documents, metadatas)
                ]
            else:
                # Return list of text strings (backward compatible)
                return results['documents'][0] if results['documents'] else []
        except Exception as e:
            self.logger.warning(f"Failed to query context from ChromaDB: {e}")
            return []

# Singleton

memory = MemoryManager()

## FILE: backend/core/models.py

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid

# ==========================================

# 1. THE UNIVERSAL ENVELOPE (Input)

# ==========================================

class AgentInput(BaseModel):
"""
The standard packet sent to ANY agent.
You never change this class, only the 'params' dictionary inside it.
"""
task: str = Field(..., description="The command name (e.g., 'scrape_leads', 'write_blog')")
user_id: str = Field("admin", description="Who is asking? (Used for RLS/Permissions)")

    # The Flexible Payload - Put ANYTHING here
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dynamic arguments (e.g., {'city': 'Auckland', 'niche': 'Plumber'})"
    )

    # Request ID for tracking logs
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

# ==========================================

# 2. THE UNIVERSAL RECEIPT (Output)

# ==========================================

class AgentOutput(BaseModel):
"""
The standard response from ANY agent.
"""
status: str = Field(..., description="'success' or 'error'")
data: Any = Field(default=None, description="The actual result (List, JSON, String, etc.)")
message: str = Field(..., description="Human readable summary for the UI")
timestamp: datetime = Field(default_factory=datetime.now)

# ==========================================

# 3. THE UNIVERSAL MEMORY (Database Record)

# ==========================================

class Entity(BaseModel):
"""
A standard format for saving things (Leads, Jobs, Tenders) to the DB.
"""
id: str = Field(default_factory=lambda: str(uuid.uuid4()))
tenant_id: str = Field(..., description="The User ID (RLS)")

    # What is this? (e.g., "lead", "job_listing", "tender")
    entity_type: str

    # The Core Data
    name: str = Field(..., description="Name of person/company/job")
    primary_contact: Optional[str] = Field(None, description="Email or Phone or URL")

    # Extra Context (e.g., {"rating": 4.5, "salary": "$100k"})
    metadata: Dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=datetime.now)

## FILE: backend/core/registry.py

# backend/core/registry.py

# --- 1. THE CODE REGISTRY (For the Kernel) ---

class AgentRegistry:
"""
Defines WHERE the code lives for each agent.
Format: "key": ("module_path", "ClassName")

    CRITICAL NOTE:
    The 'key' should match the task name exactly for clarity.
    System agents (like onboarding) bypass DNA loading because they create the config.
    """
    DIRECTORY = {
        # --- MODULE: ONBOARDING (System Agent - Creates DNA) ---
        "onboarding": ("backend.modules.onboarding.genesis", "OnboardingAgent"),

        # --- MODULE: APEX GROWTH (pSEO) ---
        # The Manager (Orchestrator)
        "manager": ("backend.modules.pseo.manager", "ManagerAgent"),

        # The Workers (Task names match Manager's _execute_task calls)
        "scout_anchors": ("backend.modules.pseo.agents.scout", "ScoutAgent"),
        "strategist_run": ("backend.modules.pseo.agents.strategist", "StrategistAgent"),
        "write_pages": ("backend.modules.pseo.agents.writer", "WriterAgent"),
        "critic_review": ("backend.modules.pseo.agents.critic", "CriticAgent"),
        "librarian_link": ("backend.modules.pseo.agents.librarian", "LibrarianAgent"),
        "enhance_media": ("backend.modules.pseo.agents.media", "MediaAgent"),
        "enhance_utility": ("backend.modules.lead_gen.agents.utility", "UtilityAgent"),
        "publish": ("backend.modules.pseo.agents.publisher", "PublisherAgent"),
        "analytics_audit": ("backend.modules.pseo.agents.analytics", "AnalyticsAgent"),

        # --- MODULE: APEX CONNECT (Lead Gen) ---
        # The Manager (Orchestrator)
        "lead_gen_manager": ("backend.modules.lead_gen.manager", "LeadGenManager"),

        # The Workers
        "sniper_agent": ("backend.modules.lead_gen.agents.sniper", "SniperAgent"),
        "sales_agent": ("backend.modules.lead_gen.agents.sales", "SalesAgent"),
        "reactivator_agent": ("backend.modules.lead_gen.agents.reactivator", "ReactivatorAgent"),
        "lead_scorer": ("backend.modules.lead_gen.agents.scorer", "LeadScorerAgent"),
        # "twilio": ("backend.modules.lead_gen.agents.twilio", "TwilioAgent"),

        # --- MODULE: SYSTEM OPERATIONS (Supervisor) ---
        # The Manager (Orchestrator)
        "system_ops_manager": ("backend.modules.system_ops.manager", "SystemOpsManager"),

        # The Workers
        "health_check": ("backend.modules.system_ops.agents.sentinel", "SentinelAgent"),
        "log_usage": ("backend.modules.system_ops.agents.accountant", "AccountantAgent"),
        "cleanup": ("backend.modules.system_ops.agents.janitor", "JanitorAgent"),
    }

# --- 2. THE FEATURE REGISTRY (For the Frontend) ---

class ModuleManifest:
"""
The App Store Catalog.
"""
CATALOG = {
"local_seo": {
"name": "Apex Growth (pSEO)",
"description": "Dominate Google Maps with auto-generated location pages.", # Updated Agent List
"agents": ["scout", "strategist", "writer", "critic", "librarian", "media", "publisher", "analytics"],
"config_required": [
"anchor_entities",
 "geo_scope"
]
},
"lead_gen": {
"name": "Apex Connect (Lead Gen)",
"description": "24/7 Lead Capture & Voice Routing.",
"agents": ["utility", "twilio"],
"config_required": [
"operations.voice_agent.forwarding_number"
 ]
}
}

    @staticmethod
    def get_user_menu():
        return {key: data['name'] for key, data in ModuleManifest.CATALOG.items()}

## FILE: backend/core/schemas.py

# backend/core/schemas.py

"""
Strict Pydantic schemas for agent task params.
Used by the kernel to validate packet.params before dispatch.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

class BaseAgentParams(BaseModel):
"""Common params many agents accept (all optional)."""
project_id: Optional[str] = None
campaign_id: Optional[str] = None
niche: Optional[str] = None

    model_config = ConfigDict(extra="allow")  # Allow context_id, request_id, etc. from main/kernel

class EmptyParams(BaseModel):
"""No params (health_check, cleanup, analytics_audit)."""
model_config = ConfigDict(extra="allow")

# --- pSEO workers (campaign_id optional; kernel/context may inject) ---

class ScoutParams(BaseAgentParams):
pass

class StrategistParams(BaseAgentParams):
pass

class WriterParams(BaseAgentParams):
pass

class CriticParams(BaseAgentParams):
pass

class LibrarianParams(BaseAgentParams):
pass

class MediaParams(BaseAgentParams):
pass

class UtilityParams(BaseAgentParams):
pass

class PublisherParams(BaseAgentParams):
limit: int = Field(default=2, ge=1, le=100)

# --- pSEO manager ---

class ManagerParams(BaseAgentParams):
action: str = Field(default="dashboard_stats")
settings: Optional[Dict[str, Any]] = None
ids: Optional[List[str]] = None
operation: Optional[str] = None
status: Optional[str] = None
draft_id: Optional[str] = None
content: Optional[str] = None

# --- Lead Gen ---

class SniperParams(BaseAgentParams):
pass

class SalesParams(BaseAgentParams):
action: str = Field(default="instant_call")
lead_id: Optional[str] = None

class ReactivatorParams(BaseAgentParams):
limit: int = Field(default=20, ge=1, le=500)

class LeadScorerParams(BaseModel):
lead_id: str = Field(..., min_length=1)
project_id: Optional[str] = None
campaign_id: Optional[str] = None

    model_config = ConfigDict(extra="allow")

class LeadGenManagerParams(BaseAgentParams):
action: str = Field(default="dashboard_stats")
lead_id: Optional[str] = None

# --- System ops ---

class LogUsageParams(BaseAgentParams):
resource: str = Field(..., min_length=1)
quantity: float = Field(..., ge=0)

class SystemOpsManagerParams(BaseModel):
action: str = Field(default="run_diagnostics")
project_id: Optional[str] = None

    model_config = ConfigDict(extra="allow")

# --- Onboarding ---

class OnboardingParams(BaseModel):
action: str = Field(default="compile_profile")
identity: Optional[Dict[str, Any]] = None
modules: Optional[List[str]] = None
project_id: Optional[str] = None
module: Optional[str] = None
name: Optional[str] = None
step: Optional[str] = None
form_data: Optional[Dict[str, Any]] = None
history: Optional[str] = None
context: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")

# --- Task -> Schema map (must match AgentRegistry.DIRECTORY keys) ---

TASK_SCHEMA_MAP = {
"onboarding": OnboardingParams,
"manager": ManagerParams,
"scout_anchors": ScoutParams,
"strategist_run": StrategistParams,
"write_pages": WriterParams,
"critic_review": CriticParams,
"librarian_link": LibrarianParams,
"enhance_media": MediaParams,
"enhance_utility": UtilityParams,
"publish": PublisherParams,
"analytics_audit": EmptyParams,
"lead_gen_manager": LeadGenManagerParams,
"sniper_agent": SniperParams,
"sales_agent": SalesParams,
"reactivator_agent": ReactivatorParams,
"lead_scorer": LeadScorerParams,
"system_ops_manager": SystemOpsManagerParams,
"health_check": EmptyParams,
"log_usage": LogUsageParams,
"cleanup": EmptyParams,
}

## FILE: backend/core/security.py

import base64
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

class SecurityCore:
"""
Encryption helper for secrets at rest.
Uses Fernet (AES128 + HMAC) with key provided via env `APEX_KMS_KEY`.
"""

    def __init__(self):
        self.logger = logging.getLogger("Apex.SecurityCore")
        key_b64 = os.getenv("APEX_KMS_KEY")
        if not key_b64:
            raise ValueError("APEX_KMS_KEY environment variable is not set.")

        try:
            # Accept either a raw Fernet key or urlsafe base64 string
            key_bytes = key_b64.encode()
            # If the key is not a valid Fernet length, try base64-decoding
            try:
                base64.urlsafe_b64decode(key_bytes)
                self.fernet = Fernet(key_bytes)
            except Exception:
                decoded = base64.urlsafe_b64decode(key_bytes)
                self.fernet = Fernet(base64.urlsafe_b64encode(decoded))
        except Exception as e:
            raise ValueError(f"Invalid APEX_KMS_KEY: {e}")

    def encrypt(self, plaintext: str) -> str:
        if plaintext is None:
            raise ValueError("Cannot encrypt None")
        token = self.fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, token: str) -> str:
        if token is None:
            raise ValueError("Cannot decrypt None")
        try:
            plaintext = self.fernet.decrypt(token.encode("utf-8"))
            return plaintext.decode("utf-8")
        except InvalidToken as e:
            self.logger.error("Failed to decrypt secret: invalid token")
            raise e

# Singleton

security_core = SecurityCore()

## FILE: backend/core/services/**init**.py

## FILE: backend/core/services/llm_gateway.py

import logging
import os
from typing import Optional

from google import genai
from google.genai import types

class LLMGateway:
"""
Centralized LLM gateway for all model calls.

    Responsibilities:
    - Single place to initialize the genai client with API key
    - Enforce default model selection (Gemini 1.5 Pro)
    - Provide lightweight retry handling and logging
    - Future hooks: cost tracking and rate limiting
    """

    def __init__(self):
        self.logger = logging.getLogger("Apex.LLMGateway")
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set.")

        self.client = genai.Client(api_key=api_key)
        self.default_model = os.getenv("APEX_LLM_MODEL", "gemini-2.5-flash")

    def generate_content(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.6,
        max_retries: int = 3,
    ) -> str:
        """
        Generate content with centralized retries and logging.
        """
        target_model = model or self.default_model
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                self.logger.info(
                    f"LLM request attempt {attempt}/{max_retries} | model={target_model}"
                )

                response = self.client.models.generate_content(
                    model=target_model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                    ),
                )

                text = (response.text or "").strip()
                if not text:
                    raise ValueError("Empty LLM response text.")

                # Hook: cost tracking / token logging can be added here
                return text

            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"LLM attempt {attempt} failed: {e}", exc_info=True
                )

        # Exhausted retries
        raise RuntimeError(
            f"LLM generation failed after {max_retries} attempts: {last_error}"
        )

    def generate_embeddings(
        self,
        texts: list[str],
        model: str = "text-embedding-004",
        max_retries: int = 3,
    ) -> list[list[float]]:
        """
        Generate embeddings using Google's embedding API.

        Args:
            texts: List of text strings to embed
            model: Embedding model to use (default: text-embedding-004)
            max_retries: Maximum number of retry attempts

        Returns:
            List of embedding vectors (list of floats)
        """
        if not texts:
            return []

        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                self.logger.debug(
                    f"Embedding request attempt {attempt}/{max_retries} | model={model} | texts={len(texts)}"
                )

                response = self.client.models.embed_content(
                    model=model,
                    contents=texts
                )

                embeddings = [e.values for e in response.embeddings]

                if not embeddings or len(embeddings) != len(texts):
                    raise ValueError(f"Embedding count mismatch: expected {len(texts)}, got {len(embeddings)}")

                return embeddings

            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"Embedding attempt {attempt} failed: {e}", exc_info=True
                )

        # Exhausted retries
        raise RuntimeError(
            f"Embedding generation failed after {max_retries} attempts: {last_error}"
        )

# Singleton instance

llm_gateway = LLMGateway()

## FILE: backend/core/services/maps_sync.py

# backend/core/services/maps_sync.py

import time
import random
import re
import logging
from playwright.sync_api import sync_playwright

logger = logging.getLogger("Apex.Scout")

def run_scout_sync(queries: list, allow_kws: list = None, block_kws: list = None):
"""
YOUR ORIGINAL LOGIC (Synchronous)
"""
try: # Normalize filters
allow_kws = [k.lower() for k in (allow_kws or [])]
block_kws = [k.lower() for k in (block_kws or [])]

        logger.info(f"SCOUT SYNC: Initializing for {len(queries)} queries...")

        master_data = []
        seen_ids = set()
        errors = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            try:
                for query in queries:
                    try:
                        logger.info(f"Scouting: {query}...")
                        url = f"https://www.google.co.nz/maps/search/{query.replace(' ', '+')}"
                        page.goto(url, timeout=60000)

                        try:
                            page.locator('button[aria-label="Accept all"]').first.click(timeout=3000)
                        except Exception as e:
                            logger.debug(f"Could not click accept button for {query}: {e}")

                        # --- LIST DETECTION ---
                        is_list = False
                        try:
                            page.wait_for_selector("div[role='feed'], h1", timeout=5000)
                            if page.locator("div[role='feed']").count() > 0:
                                is_list = True
                        except Exception as e:
                            logger.debug(f"Could not detect list for {query}: {e}")

                        if is_list:
                            # 1. INFINITE SCROLL
                            logger.debug(f"Scrolling for query: {query}")
                            last_count = 0
                            no_change_ticks = 0

                            while True:
                                page.hover("div[role='feed']")
                                page.mouse.wheel(0, 5000)
                                time.sleep(1.5)

                                current_count = page.locator("a[href*='/maps/place/']").count()
                                if current_count == last_count:
                                    no_change_ticks += 1
                                else:
                                    no_change_ticks = 0

                                last_count = current_count
                                if no_change_ticks >= 3 or current_count > 50:
                                    break

                            logger.info(f"Found {last_count} targets for query: {query}")

                            # 2. DRILL DOWN LOOP
                            for i in range(last_count):
                                try:
                                    links = page.locator("a[href*='/maps/place/']")
                                    if i >= links.count(): break
                                    target = links.nth(i)

                                    href = target.get_attribute("href")
                                    raw_name = target.get_attribute("aria-label")
                                    if not raw_name or "Search" in raw_name: continue

                                    # --- BOUNCER ---
                                    if allow_kws and not any(k in raw_name.lower() for k in allow_kws): continue
                                    if block_kws and any(k in raw_name.lower() for k in block_kws): continue

                                    # --- CLICK ---
                                    # print(f"      ⛏️  Drilling: {raw_name}...")
                                    target.click()
                                    time.sleep(2)  # Ensure phone number loads before extraction

                                    # Extract
                                    data = extract_details(page, query, raw_name, href)

                                    # Deduplicate
                                    unique_id = f"{data['name']}-{data.get('address','')[:10]}"
                                    if unique_id not in seen_ids:
                                        master_data.append(data)
                                        seen_ids.add(unique_id)
                                        logger.info(f"Captured: {raw_name} | Phone: {data['phone']}")

                                    # Back
                                    if page.locator('button[aria-label="Back"]').count() > 0:
                                        page.locator('button[aria-label="Back"]').click()
                                    else:
                                        page.goto(url); page.wait_for_selector("div[role='feed']")
                                    time.sleep(1)

                                except Exception as e:
                                    logger.warning(f"Error processing item {i} for query {query}: {e}")
                                    continue

                        else:
                            # SINGLE RESULT
                            if page.locator("h1").count() > 0:
                                raw_name = page.locator("h1").first.inner_text()

                                valid = True
                                if allow_kws and not any(k in raw_name.lower() for k in allow_kws): valid = False
                                if block_kws and any(k in raw_name.lower() for k in block_kws): valid = False

                                if valid:
                                    logger.info(f"Single Result: {raw_name}")
                                    # Wait for details to load
                                    time.sleep(2)
                                    data = extract_details(page, query, raw_name, page.url)

                                    unique_id = f"{data['name']}-{data.get('address','')[:10]}"
                                    if unique_id not in seen_ids:
                                        master_data.append(data)
                                        seen_ids.add(unique_id)
                                        logger.info(f"Captured: {raw_name} | Phone: {data.get('phone', 'N/A')}")

                    except Exception as e:
                        logger.error(f"Error processing query {query}: {e}", exc_info=True)
                        continue

            except Exception as main_e:
                logger.error(f"Critical error in scout sync: {main_e}", exc_info=True)
                try:
                    browser.close()
                except Exception as close_e:
                    logger.warning(f"Error closing browser: {close_e}")
                return {
                    "success": False,
                    "agent_name": "scout_anchors",
                    "message": str(main_e),
                    "data": None
                }
            finally:
                try:
                    browser.close()
                    logger.debug("Browser closed successfully")
                except Exception as close_e:
                    logger.warning(f"Error closing browser in finally block: {close_e}")

        return {
            "success": True,
            "agent_name": "scout_anchors",
            "message": f"Captured {len(master_data)} entities.",
            "data": master_data
        }
    except Exception as outer_e:
        # Catch any exception that happens before browser initialization
        logger.error(f"Scraper initialization failed: {outer_e}", exc_info=True)
        return {
            "success": False,
            "agent_name": "scout_anchors",
            "message": f"Scraper initialization failed: {str(outer_e)}",
            "data": None
        }

def extract_details(page, source_query, name, source_url):
data = {"name": name, "source_query": source_query, "google_maps_url": source_url, "address": None, "phone": None, "website": None, "working_hours": None}

    try:
        if page.locator('button[data-item-id="address"]').count() > 0:
            data["address"] = page.locator('button[data-item-id="address"]').first.get_attribute("aria-label").replace("Address: ", "").strip()
        if page.locator('button[data-item-id*="phone"]').count() > 0:
            data["phone"] = page.locator('button[data-item-id*="phone"]').first.get_attribute("aria-label").replace("Phone: ", "").strip()
        if page.locator('a[data-item-id="authority"]').count() > 0:
            data["website"] = page.locator('a[data-item-id="authority"]').first.get_attribute("href")

        # Extract working hours if available
        try:
            # Try multiple selectors for working hours
            working_hours_text = None

            # Method 1: Look for button with working hours data-item-id
            if page.locator('button[data-item-id*="hours"], button[data-item-id*="opening"]').count() > 0:
                hours_button = page.locator('button[data-item-id*="hours"], button[data-item-id*="opening"]').first
                working_hours_text = hours_button.get_attribute("aria-label")
                if working_hours_text:
                    working_hours_text = working_hours_text.replace("Hours: ", "").replace("Opening hours: ", "").strip()

            # Method 2: Look for text content with common patterns
            if not working_hours_text:
                # Try to find div/span with hours information
                hours_selectors = [
                    'div[data-value*="hours"]',
                    'div:has-text("Open")',
                    'div:has-text("Closed")',
                    'span:has-text("AM")',
                    'span:has-text("PM")'
                ]
                for selector in hours_selectors:
                    if page.locator(selector).count() > 0:
                        working_hours_text = page.locator(selector).first.inner_text()
                        if working_hours_text and len(working_hours_text) < 200:  # Reasonable length
                            break

            if working_hours_text:
                data["working_hours"] = working_hours_text
        except Exception as hours_e:
            logger.debug(f"Could not extract working hours for {name}: {hours_e}")

    except Exception as e:
        logger.debug(f"Error extracting details for {name}: {e}")

    return data

## FILE: backend/core/services/search_sync.py

# backend/core/services/search_sync.py

import requests
import json
import logging
from backend.core.config import settings

logger = logging.getLogger("Apex.Search")

def run_search_sync(query_objects: list):
"""
Uses Serper.dev API to find Competitors and Facts reliably.

    Args:
        query_objects: List of {"query": str, "type": str} dicts where type is "competitor" or "fact"

    Returns:
        List of result dicts with {"query": str, "title": str, "link": str, "snippet": str, "type": str}
    """
    url = "https://google.serper.dev/search"
    results = []

    # Validate API key
    if not settings.SERPER_API_KEY or len(settings.SERPER_API_KEY.strip()) == 0:
        logger.error("❌ SERPER_API_KEY not configured. Please set SERPER_API_KEY in environment variables.")
        return results

    # Count queries by type
    competitor_count = sum(1 for q in query_objects if isinstance(q, dict) and q.get("type") == "competitor")
    fact_count = len(query_objects) - competitor_count

    # Enhanced logging
    logger.info(f"Using API Key: {settings.SERPER_API_KEY[:4]}...")
    logger.info(f"Input: {len(query_objects)} queries ({competitor_count} competitors, {fact_count} facts)")

    headers = {
        'X-API-KEY': settings.SERPER_API_KEY,
        'Content-Type': 'application/json'
    }

    for idx, query_obj in enumerate(query_objects, 1):
        try:
            # Handle both old format (string) and new format (dict) for backward compatibility
            if isinstance(query_obj, dict):
                query = query_obj.get("query", "")
                query_type = query_obj.get("type", "fact")  # Default to fact if not specified
            else:
                # Legacy format: just a string
                query = str(query_obj)
                query_type = "fact"  # Default for legacy queries
                logger.warning(f"⚠️ Received legacy string query format, defaulting to 'fact' type")

            if not query:
                logger.warning(f"⚠️ Skipping empty query at index {idx}")
                continue

            logger.info(f"🔍 [{idx}/{len(query_objects)}] Processing query: {query[:60]}... (type: {query_type})")
            payload = json.dumps({"q": query, "num": 5, "gl": "nz"}) # gl=nz for New Zealand
            logger.debug(f"📤 Sending request to Serper API with payload: {payload}")

            response = requests.post(url, headers=headers, data=payload, timeout=30)

            # Log raw API response status code
            logger.info(f"📡 API Response Status: {response.status_code} for query '{query[:50]}...'")

            if response.status_code == 200:
                data = response.json()
                organic = data.get("organic", [])
                logger.info(f"✅ Query '{query[:50]}...' returned {len(organic)} organic results")

                for item in organic:
                    result_item = {
                        "query": query,
                        "title": item.get("title"),
                        "link": item.get("link"),
                        "snippet": item.get("snippet"),
                        "type": query_type  # Use preserved type from query object, not keyword guessing
                    }
                    results.append(result_item)
                    logger.debug(f"  ➕ Added: {result_item.get('title', 'No title')[:50]} (type: {query_type})")
            else:
                logger.error(f"❌ API Error {response.status_code} for query '{query}': {response.text[:200]}")

        except Exception as e:
            query_str = query_obj.get("query", str(query_obj)) if isinstance(query_obj, dict) else str(query_obj)
            logger.error(f"❌ Search Failed for query '{query_str}': {e}", exc_info=True)

    logger.info(f"📊 SEARCH SYNC COMPLETE: Processed {len(query_objects)} queries, collected {len(results)} total results")
    return results

## FILE: backend/core/services/transcription.py

"""
Transcription service using Google Gemini API.
Downloads recordings from Twilio, transcribes with Gemini, and deletes recordings to minimize costs.
"""
import logging
import os
import tempfile
import requests
from typing import Optional, Tuple
from twilio.rest import Client
from google import genai
from google.genai import types

logger = logging.getLogger("Apex.Transcription")

class TranscriptionService:
"""
Handles call transcription using Google Gemini.
Downloads MP3 from Twilio, transcribes, and optionally deletes the recording.
"""

    def __init__(self):
        self.logger = logging.getLogger("Apex.Transcription")

        # Initialize Gemini client (same pattern as llm_gateway)
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set.")

        self.gemini_client = genai.Client(api_key=google_api_key)
        self.model = os.getenv("APEX_LLM_MODEL", "gemini-2.5-flash")

        # Initialize Twilio client (for deleting recordings)
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        if twilio_sid and twilio_token:
            self.twilio_client = Client(twilio_sid, twilio_token)
        else:
            self.twilio_client = None
            self.logger.warning("⚠️ Twilio credentials not set. Recording deletion will be skipped.")

    def transcribe_recording(
        self,
        recording_url: str,
        call_sid: str,
        delete_after_transcription: bool = True
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Downloads MP3 from Twilio, transcribes with Gemini, and optionally deletes recording.

        Args:
            recording_url: Full URL to the MP3 recording (e.g., https://api.twilio.com/.../Recording.mp3)
            call_sid: Twilio Call SID (for deleting the recording)
            delete_after_transcription: If True, delete the recording from Twilio after transcription

        Returns:
            Tuple of (transcription_text, error_message)
            - transcription_text: The transcribed text, or None if failed
            - error_message: Error message if failed, or None if successful
        """
        temp_file = None
        recording_sid = None

        try:
            # 1. Extract recording SID from URL for deletion
            # URL format: https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Recordings/{RecordingSid}.mp3
            try:
                parts = recording_url.split('/Recordings/')
                if len(parts) > 1:
                    recording_sid = parts[1].replace('.mp3', '')
                    self.logger.info(f"📼 Recording SID: {recording_sid}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not extract recording SID from URL: {e}")

            # 2. Download MP3 file (with Twilio authentication if needed)
            self.logger.info(f"⬇️ Downloading recording from: {recording_url}")

            # Twilio recording URLs require Basic Auth with Account SID and Auth Token
            auth = None
            if self.twilio_client:
                # Extract credentials from Twilio client
                twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
                twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
                if twilio_sid and twilio_token:
                    from requests.auth import HTTPBasicAuth
                    auth = HTTPBasicAuth(twilio_sid, twilio_token)

            response = requests.get(recording_url, stream=True, timeout=30, auth=auth)
            response.raise_for_status()

            # 3. Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                temp_file_path = temp_file.name

            file_size = os.path.getsize(temp_file_path)
            self.logger.info(f"✅ Downloaded {file_size / 1024:.2f} KB to {temp_file_path}")

            # 4. Transcribe with Google Gemini
            self.logger.info(f"🎤 Transcribing with Google Gemini ({self.model})...")

            # Upload file to Gemini using client's files API
            # Open file and upload using the client (consistent with llm_gateway pattern)
            with open(temp_file_path, 'rb') as audio_file:
                try:
                    # Try with config first (if UploadFileConfig exists)
                    uploaded_file = self.gemini_client.files.upload(
                        file=audio_file,
                        config=types.UploadFileConfig(
                            mime_type="audio/mpeg",
                            display_name="call_recording.mp3"
                        )
                    )
                except (TypeError, AttributeError):
                    # Fallback: try without config (simpler API)
                    audio_file.seek(0)  # Reset file pointer
                    uploaded_file = self.gemini_client.files.upload(file=audio_file)
            self.logger.debug(f"📤 Uploaded file to Gemini: {uploaded_file.name}")

            try:
                # Wait for file to be processed (Gemini needs time)
                import time
                time.sleep(1)  # Brief wait for file processing

                # Request transcription from Gemini
                prompt = "Please transcribe this phone call recording verbatim. Return only the transcription text, no additional commentary, formatting, or explanations."

                response = self.gemini_client.models.generate_content(
                    model=self.model,
                    contents=[
                        types.Part.from_uri(
                            file_uri=uploaded_file.uri,
                            mime_type="audio/mpeg"
                        ),
                        prompt
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.1,  # Low temperature for accurate transcription
                    )
                )

                transcription_text = (response.text or "").strip()

                if not transcription_text:
                    raise ValueError("Empty transcription response from Gemini")

                self.logger.info(f"✅ Transcription complete: {len(transcription_text)} characters")

            finally:
                # Clean up uploaded file from Gemini
                try:
                    self.gemini_client.files.delete(name=uploaded_file.name)
                    self.logger.debug(f"🗑️ Deleted uploaded file from Gemini: {uploaded_file.name}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to delete uploaded file from Gemini: {e}")

            # 5. Delete recording from Twilio (to minimize storage costs)
            if delete_after_transcription and recording_sid and self.twilio_client:
                try:
                    self.twilio_client.recordings(recording_sid).delete()
                    self.logger.info(f"🗑️ Deleted recording {recording_sid} from Twilio")
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to delete recording {recording_sid}: {e}")
                    # Don't fail the whole operation if deletion fails

            return transcription_text, None

        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to download recording: {e}"
            self.logger.error(f"❌ {error_msg}")
            return None, error_msg

        except Exception as e:
            error_msg = f"Failed to transcribe recording: {e}"
            self.logger.error(f"❌ {error_msg}", exc_info=True)
            return None, error_msg

        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                    self.logger.debug(f"Cleaned up temp file: {temp_file_path}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to delete temp file: {e}")

# Global instance

transcription_service = TranscriptionService()

## FILE: backend/core/services/universal.py

# backend/core/services/universal.py

import asyncio
import logging
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright

logger = logging.getLogger("Apex.UniversalScraper")

class UniversalScraper:
"""
The Universal Scraper Service with Deep Scraping.
Wraps Playwright (Async) to crawl multiple pages from a website.
"""

    def __init__(self, max_pages: int = 10, max_depth: int = 2):
        """
        Initialize scraper with crawling limits.

        Args:
            max_pages: Maximum number of pages to scrape (default: 10)
            max_depth: Maximum crawl depth from homepage (default: 2)
        """
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.logger = logging.getLogger("Apex.UniversalScraper")

    async def scrape(self, url: str):
        """
        Deep scraping: Crawls multiple pages from the website.
        Returns combined content from all crawled pages.
        """
        self.logger.info(f"Starting deep scrape for URL: {url}")
        # Parse base URL
        parsed = urlparse(url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"

        data = {
            "url": url,
            "content": "",
            "title": "",
            "error": None,
            "pages_scraped": 0,
            "pages_visited": []
        }

        visited = set()
        # Seed crawl with homepage + priority context pages (About/Services/Contact)
        priority_paths = [
            "",
            "/about",
            "/about-us",
            "/services",
            "/service",
            "/practice-areas",
            "/our-services",
            "/contact",
        ]

        to_visit = []
        seen_candidates = set()
        for path in priority_paths:
            candidate = urljoin(base_domain, path)
            if candidate not in seen_candidates:
                to_visit.append((candidate, 0))
                seen_candidates.add(candidate)

        all_content = []
        homepage_title = ""

        try:
            async with async_playwright() as p:
                # Launch Browser
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-http2',
                        '--no-sandbox',
                        '--disable-setuid-sandbox'
                    ]
                )

                # Context (User Agent Spoofing)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    viewport={'width': 1920, 'height': 1080}
                )

                # Crawl pages
                while to_visit and len(visited) < self.max_pages:
                    current_url, depth = to_visit.pop(0)

                    # Skip if already visited or too deep
                    if current_url in visited or depth > self.max_depth:
                        continue

                    # Skip external links
                    if not current_url.startswith(base_domain):
                        continue

                    visited.add(current_url)

                    try:
                        page = await context.new_page()

                        # Navigate with timeout
                        try:
                            await page.goto(current_url, wait_until="networkidle", timeout=30000)
                        except Exception as nav_e:
                            # Fallback if networkidle times out
                            self.logger.debug(f"networkidle timeout for {current_url}, retrying with basic navigation: {nav_e}")
                            await page.goto(current_url, timeout=30000)

                        # Extract title (use homepage title)
                        if not homepage_title:
                            homepage_title = await page.title()
                            data["title"] = homepage_title

                        # Extract content
                        page_content = await page.evaluate("() => document.body.innerText")
                        if page_content:
                            all_content.append(f"\n\n=== Page: {current_url} ===\n{page_content}")
                            data["pages_visited"].append(current_url)

                        # If this is the homepage (depth 0), collect internal links
                        if depth < self.max_depth:
                            links = await page.evaluate("""
                                () => {
                                    const links = Array.from(document.querySelectorAll('a[href]'));
                                    return links.map(a => a.href).filter(href => href);
                                }
                            """)

                            # Add new internal links to queue
                            for link in links:
                                # Normalize URL
                                absolute_link = urljoin(current_url, link)
                                parsed_link = urlparse(absolute_link)

                                # Only add same-domain links
                                if parsed_link.netloc == parsed.netloc:
                                    # Remove fragments and query params for deduplication
                                    clean_link = f"{parsed_link.scheme}://{parsed_link.netloc}{parsed_link.path}"
                                    if clean_link not in visited and (clean_link, depth + 1) not in to_visit:
                                        to_visit.append((clean_link, depth + 1))

                        await page.close()

                        # Small delay to be respectful
                        await asyncio.sleep(0.5)

                    except Exception as e:
                        # Log but continue crawling other pages
                        self.logger.warning(f"Error scraping {current_url}: {e}", exc_info=True)
                        continue

                await browser.close()

                # Combine all content
                data["content"] = "\n".join(all_content)
                data["pages_scraped"] = len(visited)
                self.logger.info(f"Completed scraping {data['pages_scraped']} pages from {url}")

        except Exception as e:
            self.logger.error(f"Critical error during scraping of {url}: {e}", exc_info=True)
            data["error"] = str(e)

        # Truncate to save tokens, strip whitespace
        if data["content"]:
            # Limit total content to 50000 chars (up from 15000 for deep scraping)
            data["content"] = data["content"][:50000].strip()

        return data

    def log(self, message: str):
        """Logging method using proper logger."""
        self.logger.info(message)

# Standalone function for backward compatibility (optional)

async def scrape_website(url: str):
scraper = UniversalScraper()
return await scraper.scrape(url)

## FILE: backend/core/templates/lead_gen_default.yaml

# =========================================================

# APEX LEAD GEN CAMPAIGN v4.0 (The Hunter)

# =========================================================

# 1. THE SNIPER (Targeting Logic)

sniper:
enabled: true
platforms: ["facebook_groups", "trademe_jobs", "neighborly"]

# Keywords to watch for in real-time

search_terms: - "looking for {service}" - "recommend a {service}" - "urgent help needed {service}"

# Geographic filtering to prevent false positives

geo_filter: ["Auckland", "Manukau", "North Shore"]

# Negative keywords to ignore (spam/competitors)

exclusions: ["cheap", "student", "DIY", "hiring"]

# 2. THE ENGAGEMENT (The Hook)

outreach:
mode: "auto_comment" # Options: auto_comment, dm_request, notify_only

# The AI rotates these templates to avoid spam detection

response_templates: - "Hi [Name], we specialize in {service} in [Location]. We can be there in 1 hr. Call: [Phone]" - "[Name], check out our 5-star reviews for {service}. We have a slot open today."

# 3. THE SALES BRIDGE (Speed-to-Lead)

bridge:
enabled: true
destination_phone: "REQUIRED" # The Client's Mobile

# "Whisper" text played to the Client when they pick up

whisper_text: "Apex Lead Alert. Potential customer [Name] found on [Platform]. Press 1 to connect."

# SMS sent to Client if they miss the call

sms_alert: "🔥 HOT LEAD: [Name] asked for {service}. Click to call: [Link]"

## FILE: backend/core/templates/profile_template.yaml

# =========================================================

# APEX IDENTITY DNA v4.0 (The Immutable Core)

# =========================================================

identity:
project_id: "REQUIRED" # System ID (e.g., 'apex_bail_akl')
business_name: "REQUIRED" # Legal Trading Name
niche: "REQUIRED" # e.g., 'Criminal Defense', 'Emergency Plumbing'
website: "" # Primary URL
schema_type: "LocalBusiness" # Options: LegalService, Dentist, HVACBusiness

contact:
phone: "" # Public Office Number
email: "" # Public Enquiry Email
address: "" # Physical HQ Address

socials:
facebook: ""
linkedin: ""
google_maps_cid: "" # Critical for Local SEO verification

brand_brain:

# The Voice: Controls the AI Writer's personality

voice_tone: "Professional, Authoritative, Empathetic"

# The Pitch: Why a customer should buy TODAY

key_differentiators: []

# e.g., ["Available 24/7", "Fixed Fee Pricing", "Former Police Prosecutor"]

# The Wisdom: "Insider Secrets" that build instant trust

# (Injected into RAG for the Writer)

knowledge_nuggets: []

# e.g., ["Police cannot force you to unlock your phone", "Turn off mains water immediately"]

# The Defense: How to answer "Why are you so expensive?"

# (Used by Sales Agents)

common_objections: []

# e.g., ["Good lawyers aren't cheap", "We use copper, not plastic"]

# The Law: What the AI must NEVER promise

forbidden_topics: []

# e.g., ["Guaranteed acquittal", "Unconsented gas work"]

modules:

# High-level toggles only. Specific configs live in Campaigns.

local_seo:
enabled: false
lead_gen:
enabled: false
admin:
enabled: false

## FILE: backend/core/templates/pseo_default.yaml

# =========================================================

# APEX pSEO CAMPAIGN v4.0 (The Content Engine)

# =========================================================

# 1. TARGETING (The Scope)

targeting:
service_focus: "REQUIRED" # e.g., "Emergency Bail" or "Hot Water Cylinder"
geo_targets: # The Fence
cities: ["Auckland"]
suburbs: ["Manukau", "Henderson", "Albany"]

# 2. INTEL MINING (The "Anti-Hallucination" Layer)

# The Miner must fill these variables before writing starts.

mining_requirements:

# A. OFFICIAL DATA (Builds Authority)

regulatory:
enabled: true
queries: - "official filing fee for {service} in {city}" - "council permit rules for {service} {city}"
extraction_goals: ["cost", "processing_time", "official_source_url"]

# B. COMPETITOR PRICING (Builds Value)

competitor:
enabled: true
queries: - "average cost of {service} {city}" - "{service} price list {city}"
extraction_goals: ["price_range", "callout_fee"]

# C. LOCAL PROOF (Builds Trust)

geo_context:
enabled: true
target_anchors: ["Court", "Police Station", "Hardware Store", "Council Building"]

# 3. ASSET FABRICATION (The Conversion Elements)

assets:

- type: "comparison_table"
  title: "Us vs. Average {City} Rates"
  data_source: "competitor_mining"

- type: "regulatory_alert"
  title: "⚠️ Important {City} Council Rule"
  data_source: "regulatory_mining"

- type: "lead_magnet"
  style: "urgent"
  text: "Get a Free Quote in 60 Seconds"

## FILE: backend/modules/pseo/manager.py

# backend/modules/pseo/manager.py

import asyncio
from typing import Dict, Any, Optional
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class ManagerAgent(BaseAgent):
def **init**(self):
super().**init**(name="Manager")

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

        stats = {
            "anchors": len(anchors),
            "kws_total": len(kws),
            "kws_pending": len([k for k in kws if k.get("metadata", {}).get("status") == "pending"]),
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

        # Phase 1: Scout if no anchors
        if stats["anchors"] == 0:
            self.logger.info("No Anchors found. Deploying SCOUT...")
            res = await self._dispatch(kernel, "scout_anchors", base_params)
            if res.status == "error":
                return AgentOutput(status="error", message=f"Scout Failed: {res.message}")

        # Phase 2: Strategist if no keywords
        if stats["kws_total"] == 0:
            self.logger.info("No Keywords found. Deploying STRATEGIST...")
            res = await self._dispatch(kernel, "strategist_run", base_params)
            if res.status == "error":
                return AgentOutput(status="error", message=f"Strategist Failed: {res.message}")

        # Phase 3: Production line (batch each agent via kernel)
        for task_name, label in [
            ("write_pages", "WRITER"),
            ("critic_review", "CRITIC"),
            ("librarian_link", "LIBRARIAN"),
            ("enhance_media", "MEDIA"),
            ("enhance_utility", "UTILITY"),
        ]:
            self.logger.info(f"Checking {label} queue...")
            await self._run_batch(kernel, task_name, base_params)

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
                        entity_id=entity_id, new_metadata={"excluded": True}
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
                    entity_id=entity_id, new_metadata={"status": target_status}
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
        if stats["kws_pending"] > 0 and stats["1_unreviewed"] < 2:
            return {"agent_key": "write_pages", "label": "Writer", "description": "Create content", "reason": f"{stats['kws_pending']} keywords need pages"}
        if stats["kws_total"] < (stats["anchors"] * 5) and stats["anchors"] > 0:
            return {"agent_key": "strategist_run", "label": "Strategist", "description": "Generate keywords", "reason": f"Need more keywords ({stats['kws_total']}/{stats['anchors'] * 5})"}
        if stats["anchors"] == 0:
            return {"agent_key": "scout_anchors", "label": "Scout", "description": "Find locations", "reason": "No anchor locations found"}
        if stats["6_live"] > 20:
            return {"agent_key": "analytics_audit", "label": "Analytics", "description": "Analyze performance", "reason": f"{stats['6_live']} live pages ready for analysis"}
        return {"agent_key": None, "label": "Pipeline Balanced", "description": "All stages progressing well", "reason": "No immediate action needed"}

    def _format_stats(self, stats: dict) -> dict:
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

## FILE: backend/modules/system_ops/manager.py

# backend/modules/system_ops/manager.py

import logging
import asyncio
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory

class SystemOpsManager(BaseAgent):
def **init**(self):
super().**init**(name="SystemOpsManager")
self.logger = logging.getLogger("Apex.SystemOpsManager")

        # Valid actions for this manager
        self.VALID_ACTIONS = ["run_diagnostics"]

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        The Orchestrator for System Operations.

        Input params:
          - action: "run_diagnostics" (triggers health check)
        """
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

        # Validate config (if available)
        if self.config:
            if not self.config.get('modules', {}).get('system_ops', {}).get('enabled', True):
                return AgentOutput(status="error", message="System Ops module is disabled in DNA.")

        # Get and validate action parameter
        action = input_data.params.get("action", "run_diagnostics")

        # Validate action is in allowed list
        if action not in self.VALID_ACTIONS:
            self.logger.warning(f"Invalid action requested: {action}")
            return AgentOutput(
                status="error",
                message=f"Unknown action: {action}. Supported actions: {', '.join(self.VALID_ACTIONS)}"
            )

        self.logger.info(f"💼 SystemOpsManager executing action: {action} for {project_id}")

        try:
            # Action: Run Diagnostics (Health Check)
            if action == "run_diagnostics":
                self.logger.info("🔍 Deploying Sentinel Agent for health check...")

                # Lazy import to avoid circular dependency
                from backend.core.kernel import kernel

                try:
                    result = await asyncio.wait_for(
                        kernel.dispatch(
                            AgentInput(
                                task="health_check",
                                user_id=user_id,
                                params={"project_id": project_id}
                            )
                        ),
                        timeout=30  # 30 seconds max for health check
                    )
                except asyncio.TimeoutError:
                    self.logger.error("❌ Health check timed out after 30 seconds")
                    return AgentOutput(status="error", message="Health check timed out.")
                except Exception as e:
                    self.logger.error(f"❌ Health check failed: {e}", exc_info=True)
                    return AgentOutput(status="error", message=f"Health check failed: {str(e)}")

                return AgentOutput(
                    status="success",
                    data=result.data,
                    message="Health check completed."
                )

            # Unknown action (should not reach here due to validation above, but kept for safety)
            else:
                return AgentOutput(
                    status="error",
                    message=f"Unknown action: {action}. Supported actions: {', '.join(self.VALID_ACTIONS)}"
                )

        except Exception as e:
            self.logger.error(f"❌ SystemOpsManager Failed: {e}", exc_info=True)
            return AgentOutput(status="error", message=str(e))

## FILE: backend/modules/onboarding/genesis.py

# backend/modules/onboarding/genesis.py

import os
import json
import yaml
import re
from dotenv import load_dotenv
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.memory import memory
from backend.core.services.universal import UniversalScraper
from backend.core.services.llm_gateway import llm_gateway

load_dotenv()

class OnboardingAgent(BaseAgent):
def **init**(self):
super().**init**(name="Onboarding")
self.template_path = os.path.join(
os.path.dirname(os.path.dirname(os.path.dirname(**file**))),
"core",
"templates",
"profile_template.yaml"
) # Model selection for onboarding tasks (fast and cost-effective)
self.model = "gemini-2.5-flash"

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Single-shot compiler: Takes form data and generates DNA profile.
        Actions: 'compile_profile', 'create_campaign'
        """
        action = input_data.params.get("action", "compile_profile")

        if action == "compile_profile":
            return await self._compile_profile(input_data)
        elif action == "create_campaign":
            return await self._create_campaign(input_data)
        else:
            return AgentOutput(status="error", message=f"Unknown action: {action}")

    async def _compile_profile(self, input_data: AgentInput) -> AgentOutput:
        """
        Single-shot profile compiler.
        Steps: Scrape (optional) → Compile → Save → RAG
        """
        try:
            # Extract input data
            identity = input_data.params.get("identity", {})
            modules = input_data.params.get("modules", [])

            # Validate required fields
            if not isinstance(identity, dict):
                return AgentOutput(status="error", message="Invalid identity data format.")

            if not identity.get("business_name"):
                return AgentOutput(status="error", message="Business name is required.")

            if not identity.get("niche"):
                return AgentOutput(status="error", message="Niche is required.")

            if not isinstance(modules, list) or len(modules) == 0:
                return AgentOutput(status="error", message="At least one module must be selected.")

            # Validate modules
            valid_modules = ["local_seo", "lead_gen", "admin"]
            modules = [m for m in modules if m in valid_modules]
            if len(modules) == 0:
                return AgentOutput(status="error", message="No valid modules selected.")

            self.logger.info(f"Compiling profile for: {identity.get('business_name')}, modules: {modules}")

            # --- STEP A: SCRAPE (Optional) ---
            context_bio = ""
            website = identity.get("website", "").strip()

            if website:
                self.log(f"Scraping {website}...")
                try:
                    scraper = UniversalScraper()
                    raw_data = await scraper.scrape(website)

                    if raw_data and raw_data.get('content'):
                        # Extract bio/context from scraped content
                        content = raw_data.get('content', '')[:20000]  # Limit to 20k chars
                        context_bio = f"Website Content:\n{content}"
                        self.logger.info(f"Successfully scraped {len(content)} characters from website")
                    else:
                        self.logger.warning(f"Scraping returned no content for URL: {website}")
                        # Fall back to description if available
                        if identity.get("description"):
                            context_bio = f"Business Description: {identity.get('description')}"
                except Exception as e:
                    self.logger.warning(f"Scraping failed for {website}: {e}")
                    # Fall back to description if available
                    if identity.get("description"):
                        context_bio = f"Business Description: {identity.get('description')}"
            else:
                # Use description if no website
                if identity.get("description"):
                    context_bio = f"Business Description: {identity.get('description')}"

            # --- STEP B: COMPILE ---
            self.log("Compiling DNA profile...")

            # Load template
            try:
                if not os.path.exists(self.template_path):
                    return AgentOutput(status="error", message="Template file not found. System error.")

                with open(self.template_path, 'r') as f:
                    template = f.read()

                if not template:
                    return AgentOutput(status="error", message="Template file is empty. System error.")
            except Exception as e:
                self.logger.error(f"Failed to load template: {e}", exc_info=True)
                return AgentOutput(status="error", message="Failed to load template. System error.")

            # Build compilation prompt
            modules_list = ", ".join(modules)
            enable_instructions = []
            if "local_seo" in modules:
                enable_instructions.append("- Enable 'local_seo' module (set enabled: true)")
            if "lead_gen" in modules:
                enable_instructions.append("- Enable 'lead_gen' module (set enabled: true)")
            if "admin" in modules:
                enable_instructions.append("- Enable 'admin' module (set enabled: true)")

            compilation_prompt = f"""

You are Genesis, the Apex Profile Compiler. Your task is to fill the YAML template with the provided business data.

IMPORTANT: This is the simplified DNA template. It only contains:

- identity: Business information
- brand_brain: Voice, differentiators, knowledge nuggets, objections, forbidden topics
- modules: Simple toggles (enabled: true/false) - NO module-specific configuration

Module-specific configurations will be created separately as campaigns.

INPUT DATA:

- Business Name: {identity.get('business_name')}
- Niche: {identity.get('niche')}
- Phone: {identity.get('phone', '')}
- Email: {identity.get('email', '')}
- Website: {identity.get('website', '')}
- Address: {identity.get('address', '')}
- Description: {identity.get('description', '')}

SELECTED MODULES: {modules_list}

{context_bio}

TEMPLATE TO FILL:
{template}

INSTRUCTIONS:

1. Fill the 'identity' section with the provided business data.
2. Generate a valid 'project_id' from the business name (lowercase, alphanumeric + underscores/hyphens only).
3. Fill 'brand_brain' section based on the niche and context:
   - Set appropriate 'voice_tone' for the niche
   - Generate 3-5 'key_differentiators' relevant to the business
   - Generate 3-5 'knowledge_nuggets' (insider secrets) based on the niche and context
   - Generate 2-3 'common_objections' customers might have
   - Set appropriate 'forbidden_topics' for the niche
4. Module Toggles Only:
   {chr(10).join(enable_instructions)}
   - For modules NOT in the selected list, set enabled: false
   - DO NOT add any module-specific configuration (no scout_settings, sniper, sales_bridge, etc.)
   - Module-specific configs will be created later as campaigns

OUTPUT: Return ONLY the complete, valid YAML inside `yaml` tags. Do not include any other text.
"""

            try:
                response_text = llm_gateway.generate_content(
                    system_prompt="You are Genesis, the Apex Profile Compiler. Generate valid YAML configuration files.",
                    user_prompt=compilation_prompt,
                    model=self.model,
                    temperature=0.5,
                    max_retries=3
                )
            except Exception as e:
                self.logger.error(f"LLM generation failed: {e}", exc_info=True)
                return AgentOutput(status="error", message="Failed to compile profile. Please try again.")

            # Extract YAML from response
            if "```yaml" in response_text:
                yaml_content = response_text.split("```yaml")[1].split("```")[0].strip()
            elif "```" in response_text:
                # Fallback: try to extract any code block
                parts = response_text.split("```")
                if len(parts) >= 2:
                    yaml_content = parts[1].strip()
                    if yaml_content.startswith("yaml"):
                        yaml_content = yaml_content[4:].strip()
                else:
                    yaml_content = response_text.strip()
            else:
                yaml_content = response_text.strip()

            # Validate YAML can be parsed
            try:
                parsed_yaml = yaml.safe_load(yaml_content)
                if not parsed_yaml:
                    raise ValueError("YAML is empty or invalid")
            except yaml.YAMLError as e:
                self.logger.error(f"Generated YAML is invalid: {e}\nYAML preview: {yaml_content[:500]}")
                return AgentOutput(status="error", message="Generated configuration is invalid. Please try again.")

            # --- STEP C: SAVE ---
            self.log("Saving profile...")

            # Generate and sanitize project_id
            business_name = identity.get('business_name', 'new_project')
            project_id = re.sub(r'[^a-zA-Z0-9_-]', '_', business_name.lower())[:50]

            # Ensure project_id in DNA matches
            parsed_yaml['identity']['project_id'] = project_id

            # Save profile
            save_result = self._save_profile(project_id, yaml_content, input_data.user_id)
            if not save_result:
                return AgentOutput(status="error", message="Failed to save profile. Please try again.")

            self.logger.info(f"Successfully compiled and saved profile for project: {project_id}, user: {input_data.user_id}")

            return AgentOutput(
                status="complete",
                message="Profile Generated",
                data={
                    "project_id": project_id,
                    "path": f"data/profiles/{project_id}"
                }
            )

        except Exception as e:
            self.logger.error(f"Unexpected error in _compile_profile: {e}", exc_info=True)
            return AgentOutput(status="error", message=f"Failed to compile profile: {str(e)}")

    def _validate_dna_structure(self, parsed_yaml: dict) -> tuple[bool, str]:
        """Validate DNA has required fields."""
        if not isinstance(parsed_yaml, dict):
            return False, "DNA is not a valid dictionary"

        identity = parsed_yaml.get('identity', {})
        if not isinstance(identity, dict):
            return False, "Missing or invalid identity section"

        if not identity.get('project_id'):
            return False, "Missing identity.project_id (required by system)"
        if not identity.get('business_name'):
            return False, "Missing identity.business_name (required)"
        if not identity.get('niche'):
            return False, "Missing identity.niche (required)"

        return True, ""

    def _save_profile(self, project_id, content, user_id):
        """
        Save DNA profile with comprehensive error handling and validation.
        Returns True on success, False on failure.
        """
        try:
            # Validate project_id one more time before file operations
            if not project_id or not re.match(r'^[a-zA-Z0-9_-]+$', project_id):
                self.logger.error(f"Invalid project_id before save: {project_id}")
                return False

            # Parse and validate YAML structure
            try:
                parsed = yaml.safe_load(content)
                if not parsed:
                    self.logger.error("YAML content is empty after parsing")
                    return False
            except yaml.YAMLError as e:
                self.logger.error(f"YAML parsing failed: {e}")
                return False

            # Validate DNA structure
            is_valid, error_msg = self._validate_dna_structure(parsed)
            if not is_valid:
                self.logger.error(f"DNA validation failed: {error_msg}")
                return False

            # Ensure project_id in DNA matches provided project_id
            parsed['identity']['project_id'] = project_id

            # 1. Save File to Disk
            # Use absolute path from project root
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            path = os.path.join(base_dir, "data", "profiles", project_id)

            try:
                os.makedirs(path, exist_ok=True)
            except OSError as e:
                self.logger.error(f"Failed to create profile directory {path}: {e}")
                return False

            file_path = os.path.join(path, "dna.generated.yaml")
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    # Write validated/updated YAML
                    yaml.dump(parsed, f, default_flow_style=False, allow_unicode=True)
                self.logger.info(f"Saved DNA file: {file_path}")
            except IOError as e:
                self.logger.error(f"Failed to write DNA file {file_path}: {e}")
                return False

            # 2. Register in SQLite
            niche = parsed.get('identity', {}).get('niche', 'General')
            try:
                memory.register_project(user_id, project_id, niche)
                self.logger.info(f"Registered project in database: {project_id} for user {user_id}")
            except Exception as e:
                self.logger.error(f"Failed to register project in database: {e}", exc_info=True)
                # Continue anyway - file is saved, DB registration can be retried

            # --- 3. RAG INJECTION ---
            # Feed the "Brand Brain" into ChromaDB so agents can find it
            brand_brain = parsed.get('brand_brain', {})
            if not isinstance(brand_brain, dict):
                brand_brain = {}

            nugget_count = 0
            tip_count = 0

            # A. Index Knowledge Nuggets (if present)
            nuggets = brand_brain.get('knowledge_nuggets', [])
            if isinstance(nuggets, list):
                for nugget in nuggets:
                    if nugget and isinstance(nugget, str):
                        try:
                            memory.save_context(
                                tenant_id=user_id,
                                text=nugget,
                                metadata={"type": "wisdom", "source": "onboarding"},
                                project_id=project_id
                            )
                            nugget_count += 1
                        except Exception as e:
                            self.logger.warning(f"Failed to save nugget to RAG: {e}")
                            # Continue with other nuggets

            # B. Index Insider Tips
            tips = brand_brain.get('insider_tips', [])
            if isinstance(tips, list):
                for tip in tips:
                    if tip and isinstance(tip, str):
                        try:
                            memory.save_context(
                                tenant_id=user_id,
                                text=f"Insider Tip: {tip}",
                                metadata={"type": "tip", "source": "onboarding"},
                                project_id=project_id
                            )
                            tip_count += 1
                        except Exception as e:
                            self.logger.warning(f"Failed to save tip to RAG: {e}")
                            # Continue with other tips

            self.log(f"🧠 Injected {nugget_count + tip_count} wisdom nuggets into RAG Memory ({nugget_count} nuggets, {tip_count} tips).")

            return True

        except Exception as e:
            self.logger.error(f"Unexpected error in _save_profile: {e}", exc_info=True)
            return False

    async def _create_campaign(self, input_data: AgentInput) -> AgentOutput:
        """
        Creates a campaign for a module (pseo or lead_gen) with interview flow.
        Steps: interview_start → interview_loop → finalize (create campaign)
        """
        try:
            # Extract input data
            project_id = input_data.params.get("project_id")
            module = input_data.params.get("module")  # "pseo" or "lead_gen"
            name = input_data.params.get("name", "")  # Friendly campaign name
            step = input_data.params.get("step", "finalize")  # interview_start, interview_loop, finalize
            form_data = input_data.params.get("form_data", {})  # Optional form data
            history = input_data.params.get("history", "")  # Chat history for iterative filling
            context = input_data.params.get("context", {})  # Context from previous steps

            # Validate required fields
            if not project_id:
                return AgentOutput(status="error", message="project_id is required.")

            if not module or module not in ["pseo", "lead_gen"]:
                return AgentOutput(status="error", message="module must be 'pseo' or 'lead_gen'.")

            # Verify project ownership
            if not memory.verify_project_ownership(input_data.user_id, project_id):
                return AgentOutput(status="error", message="Project not found or access denied.")

            # Load DNA for context (needed for all steps)
            from backend.core.config import ConfigLoader
            config_loader = ConfigLoader()
            dna = config_loader.load_dna(project_id)
            if dna.get("error"):
                return AgentOutput(status="error", message=f"Failed to load DNA: {dna.get('error')}")

            identity = dna.get('identity', {})
            brand_brain = dna.get('brand_brain', {})

            # ===== INTERVIEW FLOW =====
            if step == "interview_start":
                # Start interview - ask first question
                if module == "pseo":
                    question = f"Great! Let's set up your pSEO campaign. First, which service or area should this campaign focus on? (e.g., 'Emergency Bail', 'Criminal Defense', 'Hot Water Cylinder')"
                else:  # lead_gen
                    question = f"Great! Let's set up your Lead Gen campaign. What type of leads are you looking for? (e.g., 'Emergency Bail Clients', 'Criminal Defense Cases')"

                return AgentOutput(
                    status="continue",
                    message=question,
                    data={
                        "reply": question,
                        "question": question,
                        "context": {"step": 0, "module": module, "answers": {}}
                    }
                )

            elif step == "interview_loop":
                # Continue interview - collect answers and ask next question
                if not isinstance(context, dict):
                    context = {}

                answers = context.get("answers", {})
                current_step = context.get("step", 0)

                # Parse user's latest answer from history
                user_answer = ""
                if history:
                    lines = history.split("\n")
                    for line in reversed(lines):
                        if line.startswith("User:"):
                            user_answer = line.replace("User:", "").strip()
                            break

                # Store answer and ask next question
                if module == "pseo":
                    if current_step == 0:
                        answers["service_focus"] = user_answer
                        current_step = 1
                        question = "Which geographic areas should we target? (e.g., 'Auckland', 'Manukau, Henderson, Albany', or 'All of New Zealand')"
                    elif current_step == 1:
                        answers["geo_targets"] = user_answer
                        current_step = 2
                        question = "What specific keywords or search terms should we prioritize? (e.g., 'emergency bail lawyer', '24/7 criminal defense', or leave blank for auto-generation)"
                    elif current_step == 2:
                        answers["keywords"] = user_answer
                        # Ready to finalize
                        question = "Perfect! I have all the information I need. Should I create the campaign now? (yes/no)"
                    else:
                        question = "Ready to create your campaign? (yes/no)"
                else:  # lead_gen
                    if current_step == 0:
                        answers["lead_type"] = user_answer
                        current_step = 1
                        question = "What geographic areas should we target for leads? (e.g., 'Auckland', 'Manukau, North Shore')"
                    elif current_step == 1:
                        answers["geo_targets"] = user_answer
                        current_step = 2
                        question = "What search terms or keywords should the sniper use to find leads? (e.g., 'need bail lawyer', 'arrested need help', or leave blank for auto-generation)"
                    elif current_step == 2:
                        answers["search_terms"] = user_answer
                        question = "Perfect! I have all the information I need. Should I create the campaign now? (yes/no)"
                    else:
                        question = "Ready to create your campaign? (yes/no)"

                # Check if user confirmed creation
                if "yes" in user_answer.lower() and current_step >= 2:
                    # User confirmed - update context and proceed to finalize
                    context["answers"] = answers
                    context["step"] = current_step
                    # Set step to finalize so the finalize block executes
                    step = "finalize"
                else:
                    # Continue interview
                    context["answers"] = answers
                    context["step"] = current_step
                    return AgentOutput(
                        status="continue",
                        message=question,
                        data={
                            "reply": question,
                            "question": question,
                            "context": context
                        }
                    )

            # ===== FINALIZE: CREATE CAMPAIGN =====
            if step == "finalize":
                # Load appropriate template
                template_name = f"{module}_default.yaml"
                template_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    "core",
                    "templates",
                    template_name
                )

                if not os.path.exists(template_path):
                    return AgentOutput(status="error", message=f"Template not found: {template_name}")

                with open(template_path, 'r') as f:
                    template = f.read()

                # Get answers from context
                if isinstance(context, dict):
                    answers = context.get("answers", {})
                else:
                    answers = {}

                # Build compilation prompt with interview answers
                compilation_prompt = f"""

You are Genesis, the Apex Campaign Creator. Fill the campaign YAML template based on the project DNA and user interview answers.

PROJECT DNA (Context):

- Business Name: {identity.get('business_name', '')}
- Niche: {identity.get('niche', '')}
- Voice Tone: {brand_brain.get('voice_tone', '')}
- Key Differentiators: {', '.join(brand_brain.get('key_differentiators', []))}

CAMPAIGN MODULE: {module.upper()}
CAMPAIGN NAME: {name}

USER INTERVIEW ANSWERS:
{json.dumps(answers, indent=2) if answers else 'No specific answers provided - use DNA context and reasonable defaults.'}

CONVERSATION HISTORY:
{history if history else 'No conversation history.'}

TEMPLATE TO FILL:
{template}

INSTRUCTIONS:

1. Fill all REQUIRED fields in the template.
2. Use the interview answers to populate:
   - For pseo: targeting.service_focus (from answers.service_focus), targeting.geo_targets (parse cities/suburbs from answers.geo_targets), mining_requirements.queries (use answers.keywords or generate based on service_focus)
   - For lead_gen: sniper.search_terms (from answers.search_terms or generate from answers.lead_type), sniper.geo_filter (parse from answers.geo_targets)
3. Use project DNA context to inform other choices.
4. For lead_gen: Use identity.phone for bridge.destination_phone if available.
5. Make the configuration practical and actionable.

OUTPUT: Return ONLY the complete, valid YAML inside `yaml` tags. Do not include any other text.
"""

                try:
                    response_text = llm_gateway.generate_content(
                        system_prompt="You are Genesis, the Apex Campaign Creator. Generate valid YAML configuration files for campaigns.",
                        user_prompt=compilation_prompt,
                        model=self.model,
                        temperature=0.5,
                        max_retries=3
                    )
                except Exception as e:
                    self.logger.error(f"LLM generation failed: {e}", exc_info=True)
                    return AgentOutput(status="error", message="Failed to generate campaign config. Please try again.")

                # Extract YAML from response
                if "```yaml" in response_text:
                    yaml_content = response_text.split("```yaml")[1].split("```")[0].strip()
                elif "```" in response_text:
                    parts = response_text.split("```")
                    if len(parts) >= 2:
                        yaml_content = parts[1].strip()
                        if yaml_content.startswith("yaml"):
                            yaml_content = yaml_content[4:].strip()
                    else:
                        yaml_content = response_text.strip()
                else:
                    yaml_content = response_text.strip()

                # Validate YAML can be parsed
                try:
                    parsed_yaml = yaml.safe_load(yaml_content)
                    if not parsed_yaml:
                        raise ValueError("YAML is empty or invalid")
                except yaml.YAMLError as e:
                    self.logger.error(f"Generated YAML is invalid: {e}\nYAML preview: {yaml_content[:500]}")
                    return AgentOutput(status="error", message="Generated campaign configuration is invalid. Please try again.")

                # Generate campaign name if not provided
                if not name:
                    service_focus = answers.get("service_focus") or parsed_yaml.get('targeting', {}).get('service_focus', '') if module == 'pseo' else answers.get("lead_type") or parsed_yaml.get('sniper', {}).get('search_terms', [''])[0] if parsed_yaml.get('sniper') else ''
                    name = f"{service_focus} - {identity.get('business_name', 'Campaign')}" if service_focus else f"{module.upper()} Campaign - {identity.get('business_name', 'Project')}"

                # Create campaign in database
                self.log("Creating campaign in database...")
                try:
                    campaign_id = memory.create_campaign(
                        user_id=input_data.user_id,
                        project_id=project_id,
                        name=name,
                        module=module,
                        config=parsed_yaml
                    )
                except Exception as e:
                    self.logger.error(f"Failed to create campaign in database: {e}", exc_info=True)
                    return AgentOutput(status="error", message="Failed to create campaign. Please try again.")

                # Save campaign YAML to disk (backup)
                self.log("Saving campaign config to disk...")
                try:
                    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                    campaign_dir = os.path.join(base_dir, "data", "profiles", project_id, "campaigns")
                    os.makedirs(campaign_dir, exist_ok=True)

                    campaign_file = os.path.join(campaign_dir, f"{campaign_id}.yaml")
                    with open(campaign_file, "w", encoding="utf-8") as f:
                        yaml.dump(parsed_yaml, f, default_flow_style=False, allow_unicode=True)
                    self.logger.info(f"Saved campaign config to: {campaign_file}")
                except Exception as e:
                    self.logger.warning(f"Failed to save campaign config to disk: {e}")
                    # Continue anyway - DB is the source of truth

                self.logger.info(f"Successfully created campaign {campaign_id} for project: {project_id}, module: {module}")

                return AgentOutput(
                    status="complete",
                    message="Campaign Created",
                    data={
                        "campaign_id": campaign_id,
                        "complete": True,
                        "project_id": project_id,
                        "module": module,
                        "name": name,
                        "config": parsed_yaml
                    }
                )

        except Exception as e:
            self.logger.error(f"Unexpected error in _create_campaign: {e}", exc_info=True)
            return AgentOutput(status="error", message=f"Failed to create campaign: {str(e)}")

## FILE: backend/modules/pseo/agents/scout.py

# backend/modules/pseo/agents/scout.py

import asyncio
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput
from backend.core.models import Entity
from backend.core.memory import memory

# Import both tools

from backend.core.services.maps_sync import run_scout_sync
from backend.core.services.search_sync import run_search_sync

class ScoutAgent(BaseAgent):
def **init**(self):
super().**init**(name="Scout")

    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Execute scout agent to gather anchor locations and intel (competitors/facts).

        Returns:
            AgentOutput with status, message, and data containing counts of saved entities
        """
        try:
            # 1. VALIDATE INPUTS & SETUP CONTEXT
            project_id = self.project_id
            user_id = self.user_id
            campaign_id = input_data.params.get("campaign_id") or self.campaign_id

            # Validate required context
            if not project_id:
                error_msg = "Missing project_id in agent context"
                self.logger.error(error_msg)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )

            if not user_id:
                error_msg = "Missing user_id in agent context"
                self.logger.error(error_msg)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )

            if not campaign_id:
                error_msg = "Missing campaign_id in params or context"
                self.logger.error(error_msg)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )

            # Load Campaign Config (The source of truth)
            try:
                campaign = memory.get_campaign(campaign_id, user_id)
                if not campaign:
                    error_msg = f"Campaign {campaign_id} not found or access denied"
                    self.logger.error(error_msg)
                    return AgentOutput(
                        status="error",
                        message=error_msg,
                        data={}
                    )
            except Exception as e:
                error_msg = f"Failed to load campaign {campaign_id}: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )

            config = campaign.get('config', {})

            if not isinstance(config, dict):
                error_msg = "Invalid campaign config format"
                self.logger.error(error_msg)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )

            # Extract from targeting section (campaign config structure)
            targeting = config.get('targeting', {})
            service = targeting.get('service_focus', config.get('service_focus', 'Service'))
            geo_targets = targeting.get('geo_targets', {}).get('cities', [])
            mining_rules = config.get('mining_requirements', {})

            # Validate geo_targets
            if not isinstance(geo_targets, list) or len(geo_targets) == 0:
                error_msg = "No geo_targets (cities) configured in campaign"
                self.logger.warning(error_msg)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )

            self.logger.info(f"🕵️ SCOUT STARTED: {service} in {geo_targets}")

            # 2. PREPARE MISSION LISTS
            map_queries = []    # For Scout (Locations)
            search_queries = [] # For Miner (Competitors/Facts) - will contain {"query": str, "type": str} dicts

            # A. Build Map Queries (Anchors)
            # e.g., "District Court in Manukau", "Police Station in Manukau"
            try:
                target_anchors = mining_rules.get('geo_context', {}).get('target_anchors', ["Landmarks"])
                if not isinstance(target_anchors, list):
                    target_anchors = ["Landmarks"]
                    self.logger.warning("Invalid target_anchors format, using default")

                for city in geo_targets:
                    if not isinstance(city, str) or not city.strip():
                        continue
                    for anchor in target_anchors:
                        if isinstance(anchor, str) and anchor.strip():
                            map_queries.append(f"{anchor.strip()} in {city.strip()}")
            except Exception as e:
                self.logger.warning(f"Error building map queries: {e}", exc_info=True)

            # B. Build Search Queries (Intel)
            # e.g., "Bail lawyer cost Manukau", "Filing fee Manukau court"
            try:
                competitor_count = 0
                regulatory_count = 0

                # 1. Competitor Queries
                competitor_config = mining_rules.get('competitor', {})
                if competitor_config.get('enabled', False):
                    base_qs = competitor_config.get('queries', [])
                    self.logger.info(f"🔍 Competitor mining enabled - found {len(base_qs) if isinstance(base_qs, list) else 0} query templates")
                    if isinstance(base_qs, list) and len(base_qs) > 0:
                        for q in base_qs:
                            if isinstance(q, str) and q.strip():
                                # If query has placeholders, expand for each city
                                if "{city}" in q or "{service}" in q:
                                    for city in geo_targets:
                                        if isinstance(city, str) and city.strip():
                                            final_query = q.replace("{service}", service).replace("{city}", city.strip())
                                            search_queries.append({
                                                "query": final_query,
                                                "type": "competitor"
                                            })
                                            competitor_count += 1
                                else:
                                    # Query is already complete, use as-is (no placeholders)
                                    search_queries.append({
                                        "query": q.strip(),
                                        "type": "competitor"
                                    })
                                    competitor_count += 1

                # 2. Regulatory Queries (marked as "fact" type)
                regulatory_config = mining_rules.get('regulatory', {})
                if regulatory_config.get('enabled', False):
                    base_qs = regulatory_config.get('queries', [])
                    self.logger.info(f"🔍 Regulatory mining enabled - found {len(base_qs) if isinstance(base_qs, list) else 0} query templates")
                    if isinstance(base_qs, list) and len(base_qs) > 0:
                        for q in base_qs:
                            if isinstance(q, str) and q.strip():
                                # If query has placeholders, expand for each city
                                if "{city}" in q or "{service}" in q:
                                    for city in geo_targets:
                                        if isinstance(city, str) and city.strip():
                                            final_query = q.replace("{service}", service).replace("{city}", city.strip())
                                            search_queries.append({
                                                "query": final_query,
                                                "type": "fact"
                                            })
                                            regulatory_count += 1
                                else:
                                    # Query is already complete, use as-is (no placeholders)
                                    search_queries.append({
                                        "query": q.strip(),
                                        "type": "fact"
                                    })
                                    regulatory_count += 1

                self.logger.info(f"✅ Built {len(search_queries)} search queries for intel gathering ({competitor_count} competitors, {regulatory_count} facts)")
            except Exception as e:
                self.logger.error(f"❌ Error building search queries: {e}", exc_info=True)

            # Validate we have at least some queries
            if len(map_queries) == 0 and len(search_queries) == 0:
                error_msg = "No queries generated from campaign config"
                self.logger.warning(error_msg)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )

            # 3. EXECUTE SERIAL MISSIONS (Sequential for debugging)
            self.logger.info(f"🚀 Launching Serial Missions: {len(map_queries)} Map Scans, {len(search_queries)} Google Searches")

            map_results_raw = None
            search_results_raw = None
            map_error = None
            search_error = None

            try:
                # STEP 1: Run Map Sync (Anchor Locations)
                if map_queries:
                    self.logger.info(f"📍 STEP 1/2: Running map_sync for {len(map_queries)} anchor queries...")
                    self.logger.info(f"📍 Map queries: {map_queries[:3]}{'...' if len(map_queries) > 3 else ''}")
                    try:
                        task_maps = asyncio.to_thread(run_scout_sync, map_queries)
                        map_results_raw = await task_maps
                        self.logger.info(f"✅ Map sync completed: {map_results_raw.get('message', 'Unknown status')}")
                    except Exception as e:
                        map_error = str(e)
                        self.logger.error(f"❌ Map sync failed: {e}", exc_info=True)
                        map_results_raw = {"success": False, "data": [], "message": map_error}
                else:
                    self.logger.info("📍 STEP 1/2: No map queries - skipping map_sync")
                    map_results_raw = {"success": True, "data": [], "message": "No map queries"}

                # STEP 2: Run Search Sync (Intel/Competitors/Facts)
                if search_queries:
                    competitor_count = sum(1 for q in search_queries if isinstance(q, dict) and q.get("type") == "competitor")
                    fact_count = len(search_queries) - competitor_count
                    self.logger.info(f"🔎 STEP 2/2: Executing search_sync with {len(search_queries)} queries via Serper API ({competitor_count} competitors, {fact_count} facts)...")
                    # Log sample queries (first 3)
                    sample_queries = [q.get("query", q) if isinstance(q, dict) else q for q in search_queries[:3]]
                    self.logger.info(f"🔎 Sample queries: {sample_queries}{'...' if len(search_queries) > 3 else ''}")
                    try:
                        task_search = asyncio.to_thread(run_search_sync, search_queries)
                        search_results_raw = await task_search
                        self.logger.info(f"📊 Search sync completed - received {len(search_results_raw) if isinstance(search_results_raw, list) else 0} results")
                        if not isinstance(search_results_raw, list):
                            self.logger.warning(f"⚠️ Search sync returned non-list result: {type(search_results_raw)}")
                            search_results_raw = []
                        elif len(search_results_raw) == 0:
                            self.logger.warning("⚠️ Search sync returned empty results - check API key and query validity")
                            self.logger.info(f"🔍 Debug: Queries sent were: {search_queries}")
                        else:
                            self.logger.info(f"✅ Successfully collected {len(search_results_raw)} search results")
                    except Exception as e:
                        search_error = str(e)
                        self.logger.error(f"❌ Search sync failed: {e}", exc_info=True)
                        self.logger.error(f"🔍 Debug: Queries that failed: {search_queries}")
                        search_results_raw = []
                else:
                    self.logger.warning("⚠️ STEP 2/2: No search queries generated - skipping search_sync")
                    self.logger.info(f"🔍 Debug: competitor.enabled={mining_rules.get('competitor', {}).get('enabled')}, regulatory.enabled={mining_rules.get('regulatory', {}).get('enabled')}")
                    search_results_raw = []

            except Exception as e:
                error_msg = f"Failed to execute parallel missions: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                return AgentOutput(
                    status="error",
                    message=error_msg,
                    data={}
                )

            # 4. PROCESS & SAVE DATA
            saved_anchors = 0
            saved_intel = 0
            save_errors = []

            try:
                # Process map results (anchor locations)
                if map_results_raw and map_results_raw.get('success', False):
                    anchor_data = map_results_raw.get('data', [])
                    if isinstance(anchor_data, list):
                        saved_anchors = self._save_anchors(anchor_data, user_id, project_id, campaign_id)
                    else:
                        self.logger.warning(f"Invalid anchor data format: {type(anchor_data)}")
                else:
                    self.logger.warning(f"Map sync failed or returned no data: {map_results_raw.get('message', 'Unknown error')}")

                # Process search results (intel)
                if isinstance(search_results_raw, list):
                    if len(search_results_raw) > 0:
                        self.logger.info(f"💾 Processing {len(search_results_raw)} search results for intel entities...")
                        saved_intel = self._save_intel(search_results_raw, user_id, project_id, campaign_id)
                        self.logger.info(f"✅ Saved {saved_intel} intel entities (competitors/facts)")
                    else:
                        self.logger.warning("⚠️ Search results list is empty - no intel to save")
                        saved_intel = 0
                else:
                    self.logger.warning(f"❌ Invalid search results format: {type(search_results_raw)}")
                    saved_intel = 0

            except Exception as e:
                error_msg = f"Error saving entities: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                save_errors.append(error_msg)

            # 5. REPORT
            status = "success"
            message_parts = [f"Intel Gathered: {saved_anchors} Locations, {saved_intel} Intel Fragments."]

            if map_error:
                message_parts.append(f"Map sync errors: {map_error}")
            if search_error:
                message_parts.append(f"Search sync errors: {search_error}")
            if save_errors:
                message_parts.append(f"Save errors: {', '.join(save_errors)}")
                status = "partial"  # Partial success if some saves failed

            if saved_anchors == 0 and saved_intel == 0:
                status = "error"
                message_parts.append("No entities were saved.")

            return AgentOutput(
                status=status,
                message=" ".join(message_parts),
                data={
                    "anchors": saved_anchors,
                    "intel": saved_intel,
                    "next_step": "Ready for Strategist" if saved_anchors > 0 or saved_intel > 0 else "Check configuration"
                }
            )

        except Exception as e:
            error_msg = f"Unexpected error in scout agent: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return AgentOutput(
                status="error",
                message=error_msg,
                data={}
            )

    def _save_anchors(self, results: List[Dict[str, Any]], user_id: str, project_id: str, campaign_id: str) -> int:
        """
        Save anchor location entities with RLS enforcement.

        Args:
            results: List of anchor location data dicts from maps_sync
            user_id: Tenant ID for RLS
            project_id: Project ID for scoping
            campaign_id: Campaign ID for scoping

        Returns:
            Count of successfully saved entities
        """
        if not results or not isinstance(results, list):
            self.logger.warning("No anchor results to save or invalid format")
            return 0

        count = 0
        seen_ids = set()

        for item in results:
            try:
                # Validate item structure
                if not isinstance(item, dict):
                    self.logger.warning(f"Invalid anchor item format: {type(item)}")
                    continue

                name = item.get('name')
                if not name or not isinstance(name, str) or not name.strip():
                    self.logger.warning("Skipping anchor with missing/invalid name")
                    continue

                # Create unique ID based on name and address
                address = item.get('address', '')[:10] if item.get('address') else ''
                unique_str = f"{name.strip()}-{address}"
                unique_id = hashlib.sha256(unique_str.encode()).hexdigest()[:16]

                # Deduplicate
                if unique_id in seen_ids:
                    self.logger.debug(f"Skipping duplicate anchor: {name}")
                    continue
                seen_ids.add(unique_id)

                # Build entity
                entity = Entity(
                    id=f"anchor_{unique_id}",
                    tenant_id=user_id,
                    project_id=project_id,
                    entity_type="anchor_location",
                    name=name.strip()[:200],  # Limit name length
                    primary_contact=item.get('phone'),  # Phone as primary contact
                    metadata={
                        "campaign_id": campaign_id,
                        "address": item.get('address'),
                        "google_maps_url": item.get('google_maps_url'),
                        "source_query": item.get('source_query'),
                        "working_hours": item.get('working_hours'),  # If available from maps_sync
                        "website": item.get('website')
                    }
                )

                # Save entity
                success = memory.save_entity(entity, project_id=project_id)
                if success:
                    count += 1
                    self.logger.debug(f"Saved anchor: {name}")
                else:
                    self.logger.warning(f"Failed to save anchor: {name}")

            except Exception as e:
                self.logger.warning(f"Error saving anchor entity: {e}", exc_info=True)
                continue

        self.logger.info(f"Saved {count} anchor locations")
        return count

    def _save_intel(self, results: List[Dict[str, Any]], user_id: str, project_id: str, campaign_id: str) -> int:
        """
        Save knowledge fragment entities (competitors/facts) with RLS enforcement.

        Args:
            results: List of search result dicts from search_sync
            user_id: Tenant ID for RLS
            project_id: Project ID for scoping
            campaign_id: Campaign ID for scoping

        Returns:
            Count of successfully saved entities
        """
        if not results or not isinstance(results, list):
            self.logger.warning("No intel results to save or invalid format")
            return 0

        count = 0
        seen_ids = set()

        for item in results:
            try:
                # Validate item structure
                if not isinstance(item, dict):
                    self.logger.warning(f"Invalid intel item format: {type(item)}")
                    continue

                # Validate required fields
                required_fields = ['title', 'link', 'type', 'query']
                if not all(field in item for field in required_fields):
                    self.logger.warning(f"Skipping intel item with missing fields: {item.keys()}")
                    continue

                title = item.get('title', '').strip()
                link = item.get('link', '').strip()

                if not title or not link:
                    self.logger.warning("Skipping intel with missing title or link")
                    continue

                # Create unique ID based on link
                uid = hashlib.sha256(link.encode()).hexdigest()[:16]

                # Deduplicate
                if uid in seen_ids:
                    self.logger.debug(f"Skipping duplicate intel: {title[:50]}")
                    continue
                seen_ids.add(uid)

                # Validate type
                intel_type = item.get('type', 'fact')
                if intel_type not in ['competitor', 'fact']:
                    intel_type = 'fact'  # Default to fact if invalid
                    self.logger.debug(f"Invalid type '{item.get('type')}', defaulting to 'fact'")

                # Build entity
                entity = Entity(
                    id=f"intel_{uid}",
                    tenant_id=user_id,
                    project_id=project_id,
                    entity_type="knowledge_fragment",
                    name=title[:200],  # Limit name length
                    primary_contact=link,  # URL as primary contact
                    metadata={
                        "campaign_id": campaign_id,
                        "type": intel_type,  # 'competitor' or 'fact'
                        "url": link,
                        "snippet": item.get('snippet', ''),
                        "query": item.get('query', '')
                    }
                )

                # Save entity to SQL DB
                success = memory.save_entity(entity, project_id=project_id)
                if success:
                    count += 1
                    self.logger.debug(f"Saved intel: {title[:50]} ({intel_type})")

                    # Also store in ChromaDB for semantic search (RAG)
                    # Create a rich text representation for embedding
                    snippet = item.get('snippet', '')
                    text_content = f"{title}. {snippet}"
                    if link:
                        text_content += f" Source: {link}"

                    # Store in vector DB with campaign scoping
                    memory.save_context(
                        tenant_id=user_id,
                        text=text_content,
                        metadata={
                            "type": "knowledge_fragment",
                            "entity_id": f"intel_{uid}",
                            "fragment_type": intel_type,  # 'competitor' or 'fact'
                            "title": title,
                            "url": link,
                            "query": item.get('query', '')
                        },
                        project_id=project_id,
                        campaign_id=campaign_id
                    )
                    self.logger.debug(f"Stored knowledge fragment in ChromaDB: {title[:50]}")
                else:
                    self.logger.warning(f"Failed to save intel: {title[:50]}")

            except Exception as e:
                self.logger.warning(f"Error saving intel entity: {e}", exc_info=True)
                continue

        self.logger.info(f"Saved {count} knowledge fragments")
        return count
