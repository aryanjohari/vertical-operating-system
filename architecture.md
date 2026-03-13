# Apex Sovereign OS — Architecture

**Version:** 1.0  
**Status:** Single source of truth for the Vertical Operating System  
**Scope:** Backend, data layer, agents, request flow, and external integrations.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Database Management](#2-database-management)
3. [Agent Breakdown](#3-agent-breakdown)
4. [Request Flow](#4-request-flow)
5. [External Integrations](#5-external-integrations)

---

## 1. System Overview

### Core Philosophy

- **Single entry point:** All agent work is triggered via `POST /api/run` with an `AgentInput` packet (`task`, `user_id`, `params`). The **Kernel** resolves the task to a registered agent, injects context (DNA + project/campaign), and runs the agent.
- **Entity-first:** Leads, drafts, keywords, campaigns, and similar concepts are **entities** in the database (`entities` table). Optional **ChromaDB** stores embeddings for RAG. State is driven by `metadata.status` (and related fields) to form a **deterministic pipeline**.
- **Event-driven, deterministic pipeline:** Each entity type (e.g. `page_draft`, `lead`) has a well-defined status progression. The dashboard and managers use **status** to decide the "next step" (e.g. `run_next_for_draft`, `run_next_for_lead`). Agents consume work items by status and update status after completion.
- **Managers orchestrate, agents execute:** **ManagerAgent** (pSEO), **LeadGenManager**, and **SystemOpsManager** handle high-level actions (e.g. `dashboard_stats`, `run_step`, `run_next_for_draft`, `run_next_for_lead`, `instant_call`) and dispatch sub-agents via the Kernel. Lead-gen webhooks only persist leads; pipeline advancement is via dashboard (“Run next”, “Connect call”).

### Key Components

| Component | Role |
|-----------|------|
| **Kernel** | Resolves `task` → agent key (exact or prefix match), loads DNA/config, verifies project ownership, injects context, runs `agent.run(packet)`. |
| **AgentRegistry** | Maps task names to module/class and metadata (`is_system_agent`, `is_heavy`, `is_system_agent_needs_context`). |
| **MemoryManager** | SQL persistence (entities, projects, campaigns, users, usage_ledger, analytics_snapshots, client_secrets) and ChromaDB RAG (save_context / query_context). |
| **ConfigLoader** | Merges project DNA (`data/profiles/{project_id}/dna.generated.yaml`) with campaign config for agent context. |

---

## 2. Database Management

### Primary store: `data/apex.db`

Database type is detected from `DATABASE_URL`: **PostgreSQL** if URL starts with `postgres://` or `postgresql://`, otherwise **SQLite**. Schema is database-agnostic (JSON/JSONB for flexible columns).

### Schema (tables)

| Table | Purpose |
|-------|---------|
| **users** | `user_id` (PK), `password_hash`, `salt`. Auth and tenant identity. |
| **projects** | `project_id` (PK), `user_id`, `niche`, `dna_path`, `created_at`. One project per tenant for context; DNA path points to generated YAML. |
| **entities** | `id` (PK), `tenant_id`, `project_id`, `entity_type`, `name`, `primary_contact`, `metadata` (JSON), `created_at`. Universal store for anchors, keywords, drafts, leads, knowledge_fragments, etc. |
| **campaigns** | `id` (PK), `project_id`, `name`, `module` (e.g. `pseo`, `lead_gen`), `status`, `config` (JSON), `stats` (JSON), `created_at`, `updated_at`. Per-project campaigns with module-specific config. |
| **client_secrets** | `user_id` (PK), `wp_url`, `wp_user`, `wp_auth_hash`. WordPress credentials (encrypted password). |
| **analytics_snapshots** | Composite PK: `tenant_id`, `project_id`, `campaign_id`, `from_date`, `to_date`, `module`. `fetched_at`, `payload` (JSON). Cached analytics by range and module. |
| **usage_ledger** | `id` (PK), `project_id`, `resource_type`, `quantity`, `cost_usd`, `timestamp`. Billing/usage (e.g. `twilio_voice`, `gemini_token`). |

Indexes: `entities` on `tenant_id`, `project_id`; `campaigns` on `project_id`, `module`, `status`; `analytics_snapshots` on tenant/project/campaign.

### Entities table and state (`metadata.status`)

- **entity_type** identifies the kind of record: `anchor_location`, `seo_keyword`, `page_draft`, `lead`, `knowledge_fragment`, etc.
- **metadata** is a JSON object. **`metadata.status`** is the primary driver of the pipeline.

**pSEO (page_draft) status progression:**

| Status | Meaning | Next agent |
|--------|---------|------------|
| `pending_writer` | Draft slot created by Strategist; not yet written | Writer |
| `draft` | Content written; awaiting review | Critic |
| `rejected` | Critic failed; can be re-reviewed or rewritten | Critic / Writer |
| `validated` | Critic passed | Librarian |
| `ready_for_media` | Internal links added | Media |
| `ready_for_utility` | Image and placeholders set | Utility |
| `ready_to_publish` | Form/call/schema injected | Publisher |
| `published` / `live` | Exported to S3 | — |

**pSEO (seo_keyword):** `pending` → (Writer consumes) or `excluded` / approved via Manager.

**pSEO (anchor_location):** `metadata.campaign_id`, `metadata.excluded`; Scout/Strategist filter by campaign and exclusion.

**Lead Gen (lead) status:** `metadata.status`: e.g. `new`, `calling`, `connected`, `won`, etc. `metadata.score`, `metadata.priority`, `metadata.source`, `metadata.page_path`, `metadata.campaign_id`, `metadata.call_sid`, `metadata.recording_url`, `metadata.scheduled_bridge_at`, `metadata.bridge_status` drive scoring, bridge, and reactivation. `page_path` records which page or URL generated the lead (from webhook payload or Referer).

Managers and agents **read** entities filtered by `tenant_id`, `project_id`, optional `campaign_id` (often in metadata), and **status**; they **write** by updating the same entity’s `metadata` (e.g. `memory.update_entity(...)` or `memory.save_entity(Entity(...))`).

### ChromaDB (RAG)

- **Path:** `data/chroma_db` (persistent).
- **Collection:** `apex_context`. Embeddings via **Google Gemini** (`gemini-embedding-001` or `APEX_EMBEDDING_MODEL`) through `GoogleEmbeddingFunction` in `memory.py`.
- **Save:** `memory.save_context(tenant_id, text, metadata, project_id, campaign_id)` stores documents with optional `project_id` and `campaign_id` in metadata.
- **Query:** `memory.query_context(tenant_id, query, n_results, project_id, campaign_id, return_metadata)` returns semantically similar text (and optionally metadata), filtered by tenant/project/campaign.
- **Use:** Writer and Scout (and any agent that needs RAG) call `query_context` for retrieval; onboarding and other flows can call `save_context` to ingest content.

---

## 3. Agent Breakdown

Agents are registered in **AgentRegistry.DIRECTORY**. Each implements `BaseAgent` and `_execute(input_data: AgentInput) -> AgentOutput`. The Kernel injects `config`, `project_id`, `user_id`, and optionally `campaign_id`.

### Registry summary

| Task key | Module path | Class | System | Heavy | Needs context |
|----------|-------------|--------|--------|-------|----------------|
| onboarding | backend.modules.onboarding.genesis | OnboardingAgent | ✓ | — | — |
| manager | backend.modules.pseo.manager | ManagerAgent | — | — | — |
| scout_anchors | backend.modules.pseo.agents.scout | ScoutAgent | — | ✓ | — |
| strategist_run | backend.modules.pseo.agents.strategist | StrategistAgent | — | ✓ | — |
| write_pages | backend.modules.pseo.agents.writer | WriterAgent | — | ✓ | — |
| critic_review | backend.modules.pseo.agents.critic | CriticAgent | — | ✓ | — |
| librarian_link | backend.modules.pseo.agents.librarian | LibrarianAgent | — | ✓ | — |
| enhance_media | backend.modules.pseo.agents.media | MediaAgent | — | ✓ | — |
| enhance_utility | backend.modules.lead_gen.agents.utility | UtilityAgent | — | — | — |
| publish | backend.modules.pseo.agents.publisher | PublisherAgent | — | ✓ | — |
| analytics_audit | backend.modules.pseo.agents.analytics | AnalyticsAgent | — | — | — |
| lead_gen_manager | backend.modules.lead_gen.manager | LeadGenManager | — | — | — |
| sales_agent | backend.modules.lead_gen.agents.sales | SalesAgent | — | ✓ | — |
| reactivator_agent | backend.modules.lead_gen.agents.reactivator | ReactivatorAgent | — | ✓ | — |
| lead_scorer | backend.modules.lead_gen.agents.scorer | LeadScorerAgent | — | — | — |
| system_ops_manager | backend.modules.system_ops.manager | SystemOpsManager | — | — | — |
| health_check | backend.modules.system_ops.agents.sentinel | SentinelAgent | ✓ | — | — |
| log_usage | backend.modules.system_ops.agents.accountant | AccountantAgent | ✓ | — | ✓ |
| cleanup | backend.modules.system_ops.agents.janitor | JanitorAgent | ✓ | — | — |

Heavy tasks run in **background** via `BackgroundTasks` when invoked from `POST /api/run`; the API returns `processing` and a `context_id` for polling. Lead-gen webhooks do **not** trigger background work: they only persist the lead; scoring and bridge run only when the user triggers `run_next_for_lead` or `instant_call` from the dashboard (deterministic, button-based).

---

### Onboarding

| Agent | Trigger | Inputs | Outputs | Logic |
|-------|---------|--------|---------|--------|
| **OnboardingAgent** | `task=onboarding`, `action=compile_profile` or `create_campaign` | `params.profile` (form), `params.module`, `params.name`, etc. | Profile/campaign created; project registered; optional wisdom/tips to ChromaDB | **Strict:** YAML template merge and validation; no LLM for compile. |

- **compile_profile:** Merges form into `profile_template.yaml`, saves DNA to `data/profiles/{project_id}`, registers project. Can save onboarding tips to RAG.
- **create_campaign:** Creates campaign entity in DB from params.

---

### pSEO (Manager)

| Agent | Trigger | Inputs | Outputs | Logic |
|-------|---------|--------|---------|--------|
| **ManagerAgent** | `task=manager`, `params.action` | `action`, `project_id`, `campaign_id`, `draft_id`, `ids`, `operation`, `status`, etc. | Stats, next_step, or result of sub-agent | **Strict:** Aggregates entities by status; dispatches to Scout/Strategist/Writer/Critic/Librarian/Media/Utility/Publisher. |

**Actions:** `dashboard_stats`, `pulse_stats`, `get_settings`, `update_settings`, `run_step`, `run_next_for_draft`, `auto_orchestrate`, `debug_run`, `intel_review`, `strategy_review`, `force_approve_draft`, bulk anchor exclude, keyword approve/exclude.

- **run_next_for_draft:** Resolves draft’s `metadata.status` and dispatches the next agent (Writer → Critic → Librarian → Media → Utility → Publisher).
- **auto_orchestrate:** Scout (if no anchors) → Strategist (if no kws/drafts) → batch Writer, Critic, Librarian, Media, Utility → Publisher.

---

### pSEO (Workers)

| Agent | Trigger | Inputs | Outputs | Logic |
|-------|---------|--------|---------|--------|
| **ScoutAgent** | `task=scout_anchors` (or prefix) | `project_id`, `campaign_id` (from context) | Counts of saved `anchor_location` and `knowledge_fragment` entities | **Hybrid:** Serper Places + Search APIs (strict); optional LLM to dedupe/classify anchors (Gemini). |
| **StrategistAgent** | `task=strategist_run` | Same | Creates `page_draft` and `seo_keyword` entities; intent from campaign `intent_clusters` | **Strict:** No LLM; reads anchors and config; Google Autocomplete (httpx) for validation. |
| **WriterAgent** | `task=write_pages` | Optional `draft_id`; else first `pending_writer` draft | One draft updated: content, meta_title, meta_description, writer prompts in metadata | **LLM:** Gemini for JSON body; Jinja2 for HTML; RAG via `query_context`. |
| **CriticAgent** | `task=critic_review` | Optional `draft_id`; else first `draft`/`rejected` | Draft status → `validated` or `rejected`; `qa_score`, `qa_notes` | **Hybrid:** Deterministic structure checks first (h1, placeholders, tel, metadata); optional LLM pass for brand/forbidden topics. |
| **LibrarianAgent** | `task=librarian_link` | Optional `draft_id`; else first `validated` | Draft content with internal links; status → `ready_for_media` | **Strict:** Links to other drafts and intel URLs; no LLM. |
| **MediaAgent** | `task=enhance_media` | Optional `draft_id`; else first `ready_for_media` | Draft with `image_main` placeholder replaced; status → `ready_for_utility` | **Strict:** Unsplash API (httpx) for image URL. |
| **UtilityAgent** | `task=enhance_utility` | Optional `draft_id`; else first `ready_for_utility` | Form/call/schema injected; status → `ready_to_publish` | **Strict:** Jinja2 form/call/schema templates; tel link check. |
| **PublisherAgent** | `task=publish` | `limit`, optional `draft_id` | S3 export (CSV + JSON training payload); draft status → `published` | **Strict:** Builds CSV/JSON, uploads to S3, updates entity. |
| **AnalyticsAgent** | `task=analytics_audit` | `project_id`, `campaign_id`, date range (from params/config) | GSC-derived analytics; optional snapshot save | **Strict:** Google Search Console API (service account); filters by live_url. |

---

### Lead Gen

Lead Gen is **deterministic and button-based** (like pSEO): the webhook only saves the lead; scoring and call bridge run only when the user clicks “Run next” or “Connect call” on the dashboard, unless YAML enables auto-bridge.

**Webhooks:** `POST /api/webhooks/lead`, `/wordpress`, `/google-ads` normalize payload (including `page_path` from payload or `Referer`), save the lead entity with `metadata.page_path`, and return `{ success, lead_id, message: "Lead captured." }`. They do **not** trigger `lead_received` or any background pipeline.

**Call bridge (YAML):** `sales_bridge.bridge_only_on_button` (default `true`) means no automatic scheduling or execution: bridge runs only when the user clicks “Connect call”. When `false`, Manager can set `scheduled_bridge_at` and `process_scheduled_bridges` (cron or API) will attempt calls within business hours.

| Agent | Trigger | Inputs | Outputs | Logic |
|-------|---------|--------|---------|--------|
| **LeadGenManager** | `task=lead_gen_manager`, `params.action` | `action`, `lead_id`, `campaign_id` | Stats, or result of Scorer/Sales/Reactivator/transcribe | **Strict orchestration:** Dispatches to Lead Scorer, Sales, Reactivator; respects `bridge_only_on_button`; no auto-invoke from webhook. |
| **LeadScorerAgent** | Invoked by Manager for `lead_received` or `run_next_for_lead`, or direct `task=lead_scorer` | `lead_id`, `project_id`, `campaign_id` | Lead `metadata` updated with `score`, `priority`, `reasoning` | **LLM:** Gemini for scoring (0–100, Low/Medium/High). |
| **SalesAgent** | Manager `instant_call` or direct `task=sales_agent` | `action=instant_call` or `notify_sms`, `lead_id` | Lead status updated; Twilio call/SMS initiated | **Strict:** Twilio REST (create call, send SMS). |
| **ReactivatorAgent** | Manager `ignite_reactivation` or direct `task=reactivator_agent` | `limit`, `project_id`, `campaign_id` | SMS sent to stale leads via Twilio | **Strict:** Twilio SMS; business rules for “stale”. |
| **UtilityAgent** | `task=enhance_utility` (shared with pSEO) | Same as pSEO; uses lead_gen campaign for form/call | Form/call/schema blocks; tel link validation | **Strict:** Same as pSEO Utility. |

Lead Gen actions: `lead_received`, `ignite_reactivation`, `instant_call`, `transcribe_call`, `process_scheduled_bridges`, `run_next_for_lead`, `dashboard_stats`. Config: `lead_gen_default.yaml` and campaign `config` (e.g. `sales_bridge.bridge_only_on_button`, `bridge_review_email`, `min_score_to_ring`, `business_hours`).

---

### System Ops

| Agent | Trigger | Inputs | Outputs | Logic |
|-------|---------|--------|---------|--------|
| **SystemOpsManager** | `task=system_ops_manager` | `action=run_diagnostics`, `project_id` | Health result from Sentinel | **Strict:** Dispatches to Sentinel. |
| **SentinelAgent** | Scheduler or `task=health_check` | (optional `project_id` for context) | `SystemHealthStatus`: database, disk, Twilio, Gemini | **Strict:** DB ping, disk space, Twilio API, env checks. |
| **AccountantAgent** | `task=log_usage` (e.g. after voice/LLM) | `project_id`, `resource`, `quantity` | Usage logged; optional over-limit signal | **Strict:** Price list from config; writes `usage_ledger`. |
| **JanitorAgent** | Scheduler (daily 3 AM) or `task=cleanup` | None (`user_id=system`) | Count of deleted files, size freed | **Strict:** Deletes old files in `logs/`, `downloads/`. |

---

## 4. Request Flow

### End-to-end: HTTP → Kernel → Agent → Database

**Lead-gen webhooks** (`POST /api/webhooks/lead`, `/wordpress`, `/google-ads`) do **not** go through the Kernel: they validate `project_id`, normalize payload (including `page_path`), save the lead entity, and return. Scoring and bridge are triggered only by dashboard actions (`run_next_for_lead`, `instant_call` via `POST /api/run`).

1. **HTTP:** Client sends `POST /api/run` with body `{ "task": "<task>", "user_id": "<set by auth>", "params": { ... } }`. Auth middleware sets `user_id` from JWT (`get_current_user`).
2. **Router (`agents.py`):** Validates body as `AgentInput`. If task is **heavy**, creates a context via `context_manager.create_context(...)` and queues `kernel.dispatch(packet)` in `BackgroundTasks`, then returns **202-style** `{ "status": "processing", "data": { "context_id": "..." } }`. Otherwise calls `await kernel.dispatch(packet)` and returns the `AgentOutput` as JSON.
3. **Kernel:**  
   - Validates `task` and `user_id`.  
   - **Resolve agent:** `_resolve_agent(task)` → exact match or prefix match (e.g. `scout_anchors_*` → `scout_anchors`).  
   - **Params validation:** If `TASK_SCHEMA_MAP` has a schema for the agent key, `params` are validated (Pydantic).  
   - **System agents** (`is_system_agent=True`): Skip DNA load; optionally inject `project_id` and verify ownership if `is_system_agent_needs_context`; then `agent.run(packet)`.  
   - **Regular agents:** Resolve `project_id` from params or `memory.get_user_project(user_id)`. Verify `memory.verify_project_ownership(user_id, project_id)`. Load config via `ConfigLoader().load(project_id, campaign_id)`. Inject `config`, `project_id`, `user_id`, `campaign_id` into agent. Run `agent.run(packet)`.  
4. **Agent:** `BaseAgent.run(packet)` sets `self.user_id` from packet and calls `_execute(input_data)`. Agent reads/writes via `memory.*` (entities, campaigns, RAG) and optional external APIs. Returns `AgentOutput(status, data, message, timestamp)`.  
5. **Database updates:** Agents call e.g. `memory.save_entity(...)`, `memory.update_entity(...)`, `memory.log_usage(...)`, `memory.save_analytics_snapshot(...)`. Status and pipeline state live in `entities.metadata` (and campaign `config`/`stats` where applicable).
6. **Response:** Router returns `{ "status": result.status, "data": result.data, "message": result.message, ... }`. For background runs, client polls `GET /api/context/{context_id}` until `status: completed` or `failed`.

### Polling async tasks

- For heavy tasks, the client receives `context_id`.  
- `GET /api/context/{context_id}` (with auth) returns context data; when the background job finishes, context is updated with `status: completed` and `result: AgentOutput.dict()` (or `failed` and error).

---

## 5. External Integrations

| Integration | Used by | Purpose |
|-------------|--------|---------|
| **Google Gemini (genai)** | LLMGateway (all LLM/embedding calls), Writer, Critic, Lead Scorer, Scout (optional), Onboarding (optional), Transcription | Text generation, embeddings (`gemini-embedding-001`), audio transcription (Files API + model). |
| **Twilio** | SalesAgent, ReactivatorAgent, LeadGenManager (transcribe flow), Voice router, SentinelAgent (health), TranscriptionService | Voice calls, SMS, recording fetch; webhook signature validation (middleware). |
| **Serper (google.serper.dev)** | ScoutAgent (via `maps_sync`, `search_sync`) | Places API: anchor discovery. Search API: competitor/fact intel. |
| **WordPress** | Webhooks only | Inbound webhook `POST /api/webhooks/wordpress` to create leads (no outbound WP REST in code). |
| **Resend / SMTP** | Email service (`email.py`); LeadGenManager | Bridge-review notifications (high-value lead alerts). |
| **Unsplash** | MediaAgent | Hero image for page drafts. |
| **Jina Reader (r.jina.ai)** | UniversalScraper (`universal.py`) | Deep scrape of URLs (used where scraper is invoked). |
| **Google Search Console** | AnalyticsAgent | GSC API (service account) for organic clicks/impressions by URL. |
| **AWS S3** | PublisherAgent, s3.py | Upload CSV/JSON per published page (export and training payload). |
| **Google Autocomplete** | StrategistAgent | `http://google.com/complete/search?client=chrome&q=...` (httpx) to validate search volume. |

### Per-agent API usage

- **ScoutAgent:** Serper Places + Serper Search; optional Gemini (dedupe/classify).  
- **StrategistAgent:** Google Autocomplete (httpx).  
- **WriterAgent:** Gemini (LLMGateway); ChromaDB (RAG).  
- **CriticAgent:** Gemini (optional second pass).  
- **MediaAgent:** Unsplash (httpx).  
- **PublisherAgent:** S3 (boto3).  
- **AnalyticsAgent:** Google Search Console (googleapiclient + service account). Domain from project DNA `identity.gsc_site_url` or `identity.website`; credentials from `backend/secrets/gcp-secret.json` or env `GSC_SERVICE_ACCOUNT_FILE`.  
- **LeadScorerAgent:** Gemini.  
- **SalesAgent:** Twilio (calls, SMS).  
- **ReactivatorAgent:** Twilio (SMS).  
- **LeadGenManager:** Twilio (recordings), Email (Resend/SMTP), Kernel (Scorer, Sales, Reactivator).  
- **SentinelAgent:** httpx (Google), Twilio REST, Memory (DB).  
- **TranscriptionService (voice/recording-status):** Twilio (recordings), Gemini (audio → text).  
- **OnboardingAgent:** Optional Gemini for tips; ChromaDB save_context.  

Credentials and feature flags are via environment variables and project/campaign config (e.g. `GOOGLE_API_KEY`, `TWILIO_*`, `SERPER_API_KEY`, `UNSPLASH_ACCESS_KEY`, `RESEND_API_KEY`, `AWS_*`, GSC service account path).

---

*This document is the single source of truth for the Apex Sovereign OS architecture. Keep it updated when adding agents, changing pipeline statuses, or integrating new services.*
