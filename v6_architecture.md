# Apex OS v6 Architecture

**Document Version:** 1.0  
**Status:** Working reference for the entire repo  
**Scope:** Backend, frontend, data flow, dependencies, and how everything fits together.

---

## Table of Contents

1. [Overview & Philosophy](#1-overview--philosophy)
2. [Repository Structure](#2-repository-structure)
3. [Request Flow: HTTP → Kernel → Agent](#3-request-flow-http--kernel--agent)
4. [Core Backend Components](#4-core-backend-components)
5. [Agent Registry & Task Resolution](#5-agent-registry--task-resolution)
6. [Config & Templates](#6-config--templates)
7. [Memory & Data Layer](#7-memory--data-layer)
8. [Modules & Agents](#8-modules--agents)
9. [Pipeline Flows (pSEO & Lead Gen)](#9-pipeline-flows-pseo--lead-gen)
10. [API Surface](#10-api-surface)
11. [Frontend](#11-frontend)
12. [External Dependencies](#12-external-dependencies)
13. [Environment & Run](#13-environment--run)

---

## 1. Overview & Philosophy

- **Single entry point:** All agent work is triggered via `POST /api/run` with an `AgentInput` (task, user_id, params). The **Kernel** resolves the task to an agent, injects config (DNA + campaign), and runs the agent.
- **Entity-first:** Leads, drafts, keywords, campaigns, and similar concepts are **entities** in the DB (`entities` table + optional ChromaDB for RAG). Status lives in `metadata.status` and drives workflows.
- **Managers orchestrate, agents execute:** **PSEOManager** and **LeadGenManager** handle actions (dashboard_stats, run_step, run_next_for_draft, lead_received, etc.) and dispatch sub-agents (Writer, Critic, Scorer, SalesAgent, etc.).
- **Phase-based control:** Each **draft** (pSEO) and **lead** (lead gen) has a clear “next step” derived from its status. The dashboard can run that step per row via `run_next_for_draft` / `run_next_for_lead`.

---

## 2. Repository Structure

```
vertical-operating-system/
├── backend/
│   ├── main.py                 # FastAPI app, lifespan, routers, /api/run not here (in agents router)
│   ├── core/
│   │   ├── agent_base.py       # BaseAgent, run() -> _execute()
│   │   ├── auth.py             # JWT get_current_user
│   │   ├── config.py           # ConfigLoader (DNA + campaign merge), Settings (env)
│   │   ├── context.py          # Redis/in-memory context for async task polling
│   │   ├── db.py               # DB factory (SQLite/PostgreSQL)
│   │   ├── kernel.py           # Dispatch: resolve task -> inject config -> run agent
│   │   ├── memory.py           # MemoryManager: entities, projects, campaigns, RAG (ChromaDB)
│   │   ├── models.py           # AgentInput, AgentOutput, Entity (Pydantic)
│   │   ├── registry.py         # AgentRegistry.DIRECTORY, HEAVY_ACTIONS_BY_TASK, ModuleManifest
│   │   ├── schemas.py          # TASK_SCHEMA_MAP (param validation per agent)
│   │   ├── schema_loader.py    # YAML -> form schema for dashboard (lead_gen_default, etc.)
│   │   ├── services/
│   │   │   ├── business_hours.py  # within_business_hours, days_of_week
│   │   │   ├── email.py           # send_email
│   │   │   ├── llm_gateway.py     # Gemini generate_content, generate_embeddings
│   │   │   ├── maps_sync.py       # Scout: map queries
│   │   │   ├── search_sync.py     # Scout: Serper + snippet extraction
│   │   │   ├── transcription.py   # Call transcription
│   │   │   └── ...
│   │   └── templates/          # YAML + Jinja (lead_gen_default.yaml, pseo_default.yaml, ...)
│   ├── modules/
│   │   ├── lead_gen/
│   │   │   ├── manager.py      # LeadGenManager: lead_received, instant_call, process_scheduled_bridges, run_next_for_lead
│   │   │   └── agents/
│   │   │       ├── utility.py  # UtilityAgent (form, schema, call button; post-Utility validator)
│   │   │       ├── scorer.py   # LeadScorerAgent
│   │   │       ├── sales.py    # SalesAgent (Twilio bridge)
│   │   │       └── reactivator.py
│   │   ├── pseo/
│   │   │   ├── manager.py      # ManagerAgent: dashboard_stats, run_step, run_next_for_draft, auto_orchestrate
│   │   │   └── agents/
│   │   │       ├── scout.py, strategist.py, writer.py, critic.py, librarian.py, media.py, publisher.py, analytics.py
│   │   │       └── utility.py  # get_local_blurb (pure helper, no LLM)
│   │   ├── onboarding/
│   │   │   └── genesis.py      # OnboardingAgent: compile_profile, create_campaign
│   │   └── system_ops/
│   │       ├── manager.py      # SystemOpsManager
│   │       └── agents/         # SentinelAgent (health_check), AccountantAgent, JanitorAgent (cleanup)
│   └── routers/
│       ├── agents.py           # POST /api/run, GET /api/context/{context_id}
│       ├── auth.py             # /api/auth/verify, register
│       ├── entities.py        # CRUD entities (get, update, delete)
│       ├── projects.py         # projects, dna, campaigns, lead-gen/process-scheduled-bridges
│       ├── schemas.py          # GET /api/schemas/campaign/lead_gen (form schema from YAML)
│       ├── system.py           # /api/health (Redis, DB, Twilio)
│       ├── voice.py            # Twilio webhooks: /api/voice/connect, status, recording-status
│       └── webhooks.py         # /api/webhooks/lead, google-ads, wordpress
├── frontend/
│   ├── app/
│   │   ├── (auth)/login, register
│   │   ├── (dashboard)/        # projects, projects/[projectId]/*, campaigns/[campaignId]
│   │   │   ├── layout.tsx
│   │   │   ├── projects/page.tsx
│   │   │   ├── projects/[projectId]/page.tsx, leads, settings, intel, strategy, quality
│   │   │   └── projects/[projectId]/campaigns/[campaignId]/page.tsx  # Phase-based drafts + Run next
│   │   └── layout.tsx, page.tsx
│   ├── components/             # Sidebar, Topbar, DynamicForm, CreateCampaignDialog, ...
│   ├── lib/
│   │   ├── api.ts              # Axios client, getProjects, getCampaign, runPseoStep, runNextForDraft, runNextForLead, ...
│   │   └── utils.ts
│   └── types/index.ts
├── data/                       # Runtime: data/apex.db, data/chroma_db, data/profiles/{project_id}/
├── docs/
│   └── LOOP_AND_CONTROL.md    # Chronological pipeline + control
├── requirements.txt
├── v5_architecture.md
└── v6_architecture.md         # This file
```

---

## 3. Request Flow: HTTP → Kernel → Agent

```
[Frontend]  POST /api/run  { task, user_id, params }
       |
       v
[routers/agents.py]  run_command()
  - get_current_user -> user_id
  - kernel.is_heavy(task, params) ?
      YES -> create_context (Redis), background_tasks.add_task(run_agent_background)
            -> return 200 { context_id }  (client polls GET /api/context/{context_id})
      NO  -> result = await kernel.dispatch(AgentInput(...))
            -> return 200 { status, data, message }
       |
       v
[core/kernel.py]  dispatch(packet)
  1. _resolve_agent(packet.task)  -> agent_key (e.g. "manager", "write_pages", "lead_gen_manager")
  2. Params validation via TASK_SCHEMA_MAP[agent_key]
  3. System agent? -> inject project_id from params; no DNA
  4. Regular agent:
     - project_id from params.niche or params.project_id or get_user_project(user_id)
     - campaign_id from params.campaign_id
     - config = ConfigLoader().load(project_id, campaign_id)  # DNA + campaign merge
     - memory.verify_project_ownership(user_id, project_id)
     - agent.project_id, agent.user_id, agent.campaign_id, agent.config = ...
  5. agent.run(packet)  -> agent._execute(AgentInput)  -> AgentOutput
  6. return AgentOutput
```

- **Heavy tasks** (Scout, Writer, Critic, lead_received, instant_call, etc.) run in the background; the client receives a `context_id` and polls `GET /api/context/{context_id}` for status/result.
- **Light tasks** (dashboard_stats, run_next_for_draft, get_settings, etc.) run synchronously; response is the `AgentOutput` JSON.

---

## 4. Core Backend Components

| Component | Path | Role |
|-----------|------|------|
| **Kernel** | `core/kernel.py` | Resolves task → agent, loads config, injects context, runs agent. Single place that connects HTTP to agent code. |
| **Memory** | `core/memory.py` | Entities (CRUD), projects, campaigns, client_secrets, usage ledger; ChromaDB RAG (save_context, query_context). Uses DB factory from `core/db.py`. |
| **ConfigLoader** | `core/config.py` | Loads DNA from `data/profiles/{project_id}/` (dna.generated.yaml, dna.custom.yaml), merges campaign config from DB; caches 300s. `merge_config(dna, campaign_config)` shallow-merges campaign into DNA. |
| **Context** | `core/context.py` | Short-lived run state for async tasks. Redis `context:{context_id}` with TTL (default 3600s); fallback in-memory dict if Redis unavailable. |
| **Auth** | `core/auth.py` | JWT validation, `get_current_user` for protected routes. |
| **Agent base** | `core/agent_base.py` | `BaseAgent.run(input_data)` validates context then calls `_execute(input_data)`; subclasses implement `_execute`. |

---

## 5. Agent Registry & Task Resolution

- **Registry:** `core/registry.py` → `AgentRegistry.DIRECTORY`: map from **task key** to `{ module_path, class_name, is_system_agent, is_heavy }`.
- **Resolution:** `kernel._resolve_agent(task)` — exact match first (e.g. `manager`), then prefix match (e.g. `write_pages` → `write_pages`). Task names are the keys used by the frontend (e.g. `manager`, `write_pages`, `lead_gen_manager`).
- **Heavy tasks:** Either `is_heavy=True` in registry or task + action in `HEAVY_ACTIONS_BY_TASK` (e.g. `lead_gen_manager` + `lead_received`). Heavy tasks get a context_id and run in background.
- **System agents:** `health_check`, `cleanup`, `log_usage`, `onboarding` — no DNA load; they get project_id from params when needed.

**Registered agents (task key → module):**

- onboarding, manager, scout_anchors, strategist_run, write_pages, critic_review, librarian_link, enhance_media, enhance_utility, publish, analytics_audit  
- lead_gen_manager, sales_agent, reactivator_agent, lead_scorer  
- system_ops_manager, health_check, log_usage, cleanup  

---

## 6. Config & Templates

- **DNA:** Per project under `data/profiles/{project_id}/`: `dna.generated.yaml`, `dna.custom.yaml`. Load order: defaults → generated → custom. Dashboard can PATCH DNA via projects API; custom is written to `dna.custom.yaml`.
- **Campaign config:** Stored in DB (campaigns table, `config` JSON). Loaded by ConfigLoader when `campaign_id` is provided; merged over DNA (campaign wins on overlapping keys).
- **Templates (YAML):** Under `backend/core/templates/`: e.g. `lead_gen_default.yaml`, `pseo_default.yaml`, `profile_template.yaml`. Define defaults and structure; schema_loader turns them into form schemas for the dashboard (`GET /api/schemas/campaign/lead_gen`).
- **Jinja:** Form, schema, and call-button snippets can be overridden per campaign (keys in lead_gen config: `form_template`, `schema_template`, `call_button_template`). File fallbacks live under `core/templates/` (e.g. lead_gen_form.html).

---

## 7. Memory & Data Layer

- **SQLite/PostgreSQL:** `memory.db_path` (e.g. `data/apex.db`). Tables: users, projects, campaigns, entities, client_secrets, usage_ledger (if created). RLS by `tenant_id` (user_id).
- **Entities:** `entity_type` + `metadata` drive behavior. Important types: `lead`, `page_draft`, `seo_keyword`, `anchor_location`, `knowledge_fragment`. Status and pipeline state live in `metadata` (e.g. `metadata.status`, `metadata.campaign_id`, `metadata.scheduled_bridge_at`).
- **MemoryManager methods (main):**  
  `get_entities`, `get_entity`, `save_entity`, `update_entity`, `delete_entity`  
  `get_projects`, `get_campaign`, `get_campaigns_by_project`, `create_campaign`, `update_campaign_config`  
  `get_client_secrets`, `save_client_secrets`  
  `verify_project_ownership`, `get_user_project`  
  `save_context`, `query_context` (ChromaDB RAG)  
  `get_monthly_spend`, usage ledger helpers  

- **ChromaDB (vector):** Used for RAG. Embeddings via `llm_gateway.generate_embeddings` (Google). `save_context` is called by Scout and Genesis; `query_context` is used by Writer to pull knowledge fragments for a keyword. Filtered by tenant_id, project_id, campaign_id.

---

## 8. Modules & Agents

### pSEO (manager + pipeline agents)

- **ManagerAgent** (`pseo/manager.py`): Actions: `dashboard_stats`, `pulse_stats`, `get_settings`, `update_settings`, `run_step`, **`run_next_for_draft`**, `auto_orchestrate`, `debug_run`, `intel_review`, `strategy_review`, `force_approve_draft`. Uses `DRAFT_STATUS_TO_NEXT_STEP` to map draft status → next step; `run_next_for_draft(draft_id)` dispatches the right agent with `draft_id`.
- **ScoutAgent:** Fetches anchors and intel; writes anchors, knowledge_fragments; calls `memory.save_context` for RAG.
- **StrategistAgent:** Builds keywords / intent clusters; creates `page_draft` entities with status `pending_writer` (or legacy seo_keyword flow).
- **WriterAgent:** Reads pending drafts or keywords, pulls RAG via `query_context`, calls LLM for structured JSON, renders Jinja page body, writes/updates `page_draft` (status `draft`). Accepts optional `draft_id` / `keyword_id`.
- **CriticAgent:** Reviews drafts (deterministic structure + optional LLM); sets status `validated` or `rejected`. Accepts optional `draft_id`.
- **LibrarianAgent:** Injects internal links into validated drafts; sets status `ready_for_media`. Gate: run only when all campaign drafts validated (configurable). Accepts optional `draft_id`.
- **MediaAgent:** Fetches image (e.g. Unsplash), injects into draft; status → `ready_for_utility`. Accepts optional `draft_id`.
- **UtilityAgent** (lead_gen): Injects form, JSON-LD schema, call button; post-Utility validator (webhook path, tel link, JSON-LD). Status → `ready_to_publish` or `utility_validation_failed`. Accepts optional `draft_id`.
- **PublisherAgent:** Publishes `ready_to_publish` drafts to WordPress (or configured CMS). Accepts optional `draft_id`.

### Lead Gen

- **LeadGenManager** (`lead_gen/manager.py`): Actions: `lead_received`, `ignite_reactivation`, `instant_call`, **`process_scheduled_bridges`**, **`run_next_for_lead`**, `transcribe_call`, `dashboard_stats`. Resolves campaign; loads config; dispatches scorer, sales_agent, etc.
- **LeadScorerAgent:** Scores a lead (LLM); writes score into lead metadata.
- **SalesAgent:** Twilio: call boss (destination_phone), whisper, on keypress bridge to customer; writes call_sid, recording_url into lead.
- **UtilityAgent** (same as above): Used in pSEO pipeline for form/schema/call injection.

### Onboarding

- **OnboardingAgent** (`onboarding/genesis.py`): `compile_profile` (form-based DNA generation), `create_campaign` (creates campaign in DB from form_data using schema + template).

### System ops

- **SentinelAgent:** health_check.  
- **AccountantAgent:** log_usage.  
- **JanitorAgent:** cleanup (scheduled).  

---

## 9. Pipeline Flows (pSEO & Lead Gen)

### pSEO (phase-based, row control)

1. **Scout** → anchors + intel (and RAG `save_context`).  
2. **Strategist** → keywords / drafts (`pending_writer`).  
3. **Writer** → draft (status `draft`).  
4. **Critic** → `validated` or `rejected`.  
5. **Librarian** → `ready_for_media`.  
6. **Media** → `ready_for_utility`.  
7. **Utility** → `ready_to_publish` or `utility_validation_failed`.  
8. **Publisher** → `published`.

- **Run next for draft:** Manager action `run_next_for_draft` with `draft_id`; manager maps status → step and dispatches that agent with `draft_id` so only that row is processed.
- **Run step:** Single agent run for the whole campaign (first eligible item) via `run_step` + `step` (e.g. `critic_review`).  
- **Auto-orchestrate:** Scout/Strategist if needed, then batch runs Writer → Critic → Librarian → Media → Utility → Publisher (each up to N times).

### Lead Gen (event + phase-based)

1. **Webhook** (e.g. `/api/webhooks/lead`, WordPress, Google Ads) creates **lead** entity.  
2. **lead_received** (or **run_next_for_lead** for “Score”): LeadScorer runs; if score ≥ `min_score_to_ring`, set `scheduled_bridge_at` = now + `bridge_delay_minutes`, `bridge_status = "scheduled"`, send email.  
3. **process_scheduled_bridges** (cron or API): Find leads with `scheduled_bridge_at <= now`, `bridge_status == "scheduled"`, within business_hours + days_of_week; dispatch **instant_call** for each; set `bridge_attempted`.  
4. **instant_call** (or “Run next (Bridge)”): SalesAgent runs Twilio bridge.

- **Business hours:** `core/services/business_hours.py` — `within_business_hours(config)` uses `modules.lead_gen.sales_bridge.business_hours` (timezone, start_hour, end_hour, **days_of_week**) and optional holidays.

---

## 10. API Surface

| Area | Endpoints | Notes |
|------|-----------|--------|
| **Agents** | `POST /api/run`, `GET /api/context/{context_id}` | Single entry for all agent work; context for async polling. |
| **Auth** | `POST /api/auth/verify`, `POST /api/auth/register` | JWT + user creation. |
| **Projects** | `GET/POST /api/projects`, `GET/PUT /api/projects/{id}/dna`, `POST /api/projects/{id}/lead-gen/process-scheduled-bridges` | Projects CRUD, DNA, scheduled bridges. |
| **Campaigns** | `GET/POST /api/projects/{id}/campaigns`, `GET/PATCH /api/projects/{id}/campaigns/{cid}` | Campaign list, single get, config update. |
| **Entities** | `GET /api/entities`, `PATCH /api/entities/{id}`, `DELETE /api/entities/{id}` | Filter by type, project; update/delete. |
| **Schemas** | `GET /api/schemas/campaign/lead_gen` | Form schema from lead_gen_default.yaml. |
| **System** | `GET /api/health` | Component status (Redis, DB, Twilio). |
| **Voice** | `POST /api/voice/connect`, status, recording-status | Twilio webhooks. |
| **Webhooks** | `POST /api/webhooks/lead`, google-ads, wordpress | Inbound lead/form ingestion. |
| **Settings** | `GET/POST /api/settings` | WordPress credentials (client_secrets). |

- All under `/api` except `/` and `/health`. Auth: Bearer token; `get_current_user` on protected routes.

---

## 11. Frontend

- **Stack:** Next.js (App Router), TypeScript, axios (api.ts), sonner (toast).
- **Auth:** Token in memory/localStorage; api interceptors add Bearer, redirect to login on 401.
- **Key routes:**  
  `/` → home; `/login`, `/register`;  
  `/projects` → list; `/projects/[projectId]` → overview;  
  `/projects/[projectId]/leads` → leads table + “Run next (Score/Bridge)” per lead;  
  `/projects/[projectId]/settings` → DNA + campaign settings (schema-driven form for project/campaign);  
  `/projects/[projectId]/campaigns/[campaignId]` → pSEO campaign: stats, phase list, drafts table with **Run next (Write|Review|Link|…)** per draft;  
  `/projects/[projectId]/intel`, `strategy`, `quality` → intel/strategy/quality UIs.
- **API client** (`lib/api.ts`): `getProjects`, `getCampaign`, `getCampaigns`, `getCampaignDrafts`, `getPseoStats`, `runPseoStep`, **`runNextForDraft`**, **`runNextForLead`**, `dispatchTask`, `getEntities`, `updateEntity`, `connectCall`, etc. Each call is a separate HTTP request (no batching).

---

## 12. External Dependencies

| Dependency | Purpose | Where used |
|------------|---------|------------|
| **SQLite / PostgreSQL** | Entities, projects, campaigns, users, secrets, usage | memory.py, db.py |
| **Redis** | Context for async task polling (TTL) | context.py; optional, fallback in-memory |
| **ChromaDB** | Vector store for RAG | memory.py (save_context, query_context); Writer, Scout, Genesis |
| **Google Gemini** | LLM (generate_content), embeddings (text-embedding-005) | llm_gateway.py; Writer, Critic, Scorer, Scout, etc. |
| **Twilio** | Voice (bridge), SMS (reactivator) | voice.py, lead_gen/agents/sales.py, reactivator.py |
| **Serper** | Search snippets for Scout | search_sync.py, config SERPER_API_KEY |
| **Google Maps** | Scout map queries | maps_sync.py |
| **Unsplash** | Images for Media agent | pseo/agents/media.py |
| **SMTP** | Bridge review email, notifications | core/services/email.py |
| **WordPress** | Publish target (CMS) | publisher.py, client_secrets (wp_url, wp_user, wp_password) |

- **requirements.txt:** fastapi, uvicorn, pydantic, google-genai, chromadb, sqlalchemy, aiosqlite, psycopg2-binary, redis, pyjwt, pyyaml, jinja2, twilio, httpx, apscheduler, etc.

---

## 13. Environment & Run

- **Backend:** `.env` in project root. Key vars: `SERPER_API_KEY`, `GOOGLE_API_KEY` (or Gemini), `REDIS_URL`, `REDIS_TTL_SECONDS`, `DATABASE_URL` (or SQLite via path), `TWILIO_*`, `UNSPLASH_ACCESS_KEY`, `NEXT_PUBLIC_APP_URL` / `APP_URL`, etc.  
- **Run:** `uvicorn backend.main:app --reload` (default port 8000).  
- **Startup (lifespan):** Create usage table, init DB factory, start APScheduler (health check interval, cleanup daily at 3 AM).  
- **Frontend:** Next.js dev server (e.g. port 3000); `NEXT_PUBLIC_API_URL` points to backend.

---

## Quick Reference: What Depends on What

- **Kernel** depends on: Registry, ConfigLoader, Memory (verify_project_ownership, get_user_project), TASK_SCHEMA_MAP.  
- **Agents** depend on: Memory (get_entities, save_entity, update_entity, query_context, …), Config (injected), LLM gateway (Writer, Critic, Scorer, …), business_hours (LeadGenManager), email (LeadGenManager).  
- **Manager** actions depend on: Kernel (dispatch), Memory (get_campaign, get_entities, update_entity, …), Config (campaign + DNA).  
- **Frontend** depends on: Backend API (all endpoints above); no direct DB/Redis/ChromaDB.  
- **Config** depends on: `data/profiles/`, YAML files, campaign config in DB.  
- **Memory** depends on: DB factory (SQLite/PostgreSQL), ChromaDB (and embedding function via LLM gateway).

This document is the v6 working architecture and flow reference for the repo.
