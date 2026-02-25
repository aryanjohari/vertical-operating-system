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
| **Vector**          | ChromaDB + Google `gemini-embedding-001`     | RAG (brand brain, knowledge fragments)               |
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
- **Embeddings:** `GoogleEmbeddingFunction` via LLM Gateway (`gemini-embedding-001`).
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
