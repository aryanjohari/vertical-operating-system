# Apex OS v5 Architecture: The "Titanium" Refactor

**Document Version:** 1.0  
**Date:** February 2, 2026  
**Status:** Post-Refactor | Frontend Rebuild Spec

---

## Table of Contents

1. [High-Level System Architecture](#1-high-level-system-architecture)
2. [The Data Contract (The "Source of Truth")](#2-the-data-contract-the-source-of-truth)
3. [Module Deep Dives (The Flows)](#3-module-deep-dives-the-flows)
4. [The API Surface (For Frontend Refactor)](#4-the-api-surface-for-frontend-refactor)
5. [Market Fit & Stress Test Analysis](#5-market-fit--stress-test-analysis)

---

## 1. High-Level System Architecture

### The Flow

```mermaid
flowchart TB
    User["User (Agency Owner)"]
    Frontend["Frontend (Next.js 14)"]
    FastAPI["FastAPI Backend"]
    Kernel["Event-Driven Kernel"]

    subgraph Managers["Module Managers (Orchestrators)"]
        PSEOManager["pSEO Manager"]
        LeadGenManager["Lead Gen Manager"]
    end

    subgraph Agents["Specialized Agents"]
        direction LR
        Scout["Scout (Intel)"]
        Strategist["Strategist (Keywords)"]
        Writer["Writer (Content)"]
        Critic["Critic (QA)"]
        Librarian["Librarian (Links)"]
        Media["Media (Images)"]
        Utility["Utility (Forms)"]
        Publisher["Publisher (Deploy)"]
        Scorer["Scorer (LLM Judge)"]
        Sales["Sales Bridge (Twilio)"]
        Reactivator["Reactivator (SMS)"]
    end

    subgraph Memory["Memory Layer"]
        SQLite["SQLite/PostgreSQL (Entities)"]
        ChromaDB["ChromaDB (RAG Context)"]
    end

    subgraph External["External APIs"]
        OpenAI["OpenAI GPT-4"]
        Gemini["Google Gemini"]
        Twilio["Twilio (Voice/SMS)"]
        Unsplash["Unsplash (Images)"]
        Maps["Google Maps API"]
    end

    User -->|Creates Campaigns| Frontend
    Frontend -->|POST /api/run| FastAPI
    FastAPI -->|Dispatch AgentInput| Kernel
    Kernel -->|Route by task| Managers

    PSEOManager -->|Orchestrates Pipeline| Scout
    Scout --> Strategist --> Writer --> Critic --> Librarian --> Media --> Utility --> Publisher

    LeadGenManager -->|Orchestrates Inbound| Scorer
    Scorer --> Sales --> Reactivator

    Agents -->|Read/Write| Memory
    Agents -->|LLM Calls| OpenAI
    Agents -->|Embeddings| Gemini
    Writer -->|Intelligence| ChromaDB
    Scorer -->|Intelligence| ChromaDB
    Sales -->|Bridge Calls| Twilio
    Reactivator -->|SMS Campaigns| Twilio
    Scout -->|Scrape Intel| Maps
    Media -->|Fetch Images| Unsplash
    Publisher -->|Deploy HTML| External

    Memory -->|Entity Lifecycle| SQLite
    Memory -->|RAG Context| ChromaDB
```

### Philosophy: Entity-First Design

**Core Principle:** Everything is a row in the database. No ephemeral state. No hidden pipelines.

1. **Universal Entity Model**

   - All system objects (leads, keywords, page drafts, campaigns) inherit from the same `Entity` schema.
   - Each entity has: `id`, `tenant_id` (RLS), `entity_type`, `name`, `primary_contact`, `metadata` (JSON), `created_at`.
   - Status transitions live in `metadata.status` and drive all workflows.

2. **Event-Driven Kernel**

   - Single entry point: `POST /api/run` with `AgentInput { task, user_id, params }`.
   - Kernel validates, routes to the correct agent, injects context (project DNA, campaign config).
   - Agents return `AgentOutput { status, data, message, timestamp }`.
   - Heavy tasks (Scout, Writer) run in background with context polling via `GET /api/context/{context_id}`.

3. **Module Managers as Orchestrators**

   - `PSEOManager`: Conducts the linear pipeline (Scout → Publisher).
   - `LeadGenManager`: Conducts the inbound flow (Webhook → Scorer → Bridge).
   - Managers own business logic; agents own execution.

4. **Memory Abstraction**
   - SQL for entity CRUD (RLS enforced at DB layer: `tenant_id = user_id`).
   - ChromaDB for RAG context (competitor intel, knowledge fragments) with Google embeddings.
   - ConfigLoader for campaign DNA (YAML merged: base DNA + campaign overrides).

---

## 2. The Data Contract (The "Source of Truth")

### Supported Entity Types

| Entity Type          | Purpose                                                      | Owner Module | Typical Lifecycle                                        |
| -------------------- | ------------------------------------------------------------ | ------------ | -------------------------------------------------------- |
| `anchor_location`    | Google Maps places used as content anchors                   | pSEO         | `pending` → `validated` → `active`                       |
| `seo_keyword`        | Keywords derived from anchors (e.g., "bail lawyer auckland") | pSEO         | `pending` → `processing` → `mapped`                      |
| `page_draft`         | HTML pages in various stages of completion                   | pSEO         | `draft` → `validated` → `ready_to_publish` → `published` |
| `knowledge_fragment` | Scraped intel (competitors, regulations) stored as RAG       | pSEO         | `raw` → `processed`                                      |
| `lead`               | Inbound leads from forms/webhooks                            | Lead Gen     | `new` → `scored` → `calling` → `won`/`lost`              |
| `campaign`           | Configuration container (targeting, settings)                | Both         | `DRAFT` → `ACTIVE` → `PAUSED`                            |

### Lifecycle State Machines

#### `seo_keyword` (pSEO)

```mermaid
stateDiagram-v2
    [*] --> pending: Created by Strategist
    pending --> processing: Writer picks it up
    processing --> mapped: Content generated
    mapped --> rejected: Critic fails QA
    rejected --> processing: Re-write requested
    mapped --> [*]: Final state (Published)
```

**Critical Fields:**

- `metadata.status`: Current state
- `metadata.campaign_id`: Scoping to campaign
- `metadata.anchor_id`: Link back to anchor location
- `metadata.priority_score`: Strategist ranking (0-100)

#### `page_draft` (pSEO Pipeline)

```mermaid
stateDiagram-v2
    [*] --> draft: Writer creates HTML
    draft --> rejected: Critic rejects (quality)
    rejected --> draft: Re-write cycle
    draft --> validated: Critic approves
    validated --> ready_for_media: Librarian adds links
    ready_for_media --> ready_for_utility: Media adds images
    ready_for_utility --> ready_to_publish: Utility adds forms/schema
    ready_to_publish --> published: Publisher deploys to WordPress
    published --> [*]: Live on production
```

**Critical Fields:**

- `metadata.status`: Pipeline stage
- `metadata.content`: HTML string
- `metadata.keyword_id`: Link to keyword entity
- `metadata.campaign_id`: Scoping
- `metadata.rejection_reason`: If rejected by Critic
- `metadata.seo_score`: Critic QA score (0-100)
- `metadata.wp_post_id`: WordPress post ID after publish

#### `lead` (Lead Gen Inbound)

```mermaid
stateDiagram-v2
    [*] --> new: Webhook received
    new --> scored: Scorer assigns intent score
    scored --> calling: Sales Bridge triggers (score >= threshold)
    scored --> archived: Low score, skip bridge
    calling --> connected: Call answered
    calling --> no_answer: Voicemail / busy
    connected --> won: Qualified & booked
    connected --> lost: Disqualified
    no_answer --> reactivate: Reactivator SMS campaign
    reactivate --> won: Re-engaged
    reactivate --> lost: No response
    archived --> [*]
    won --> [*]
    lost --> [*]
```

**Critical Fields:**

- `metadata.status`: Current state
- `metadata.score`: LLM Judge score (0-100)
- `metadata.intent`: "high", "medium", "low"
- `metadata.urgency`: Boolean (urgent language detected)
- `metadata.source`: "wordpress_form", "calculator", "google_ads"
- `metadata.campaign_id`: Scoping
- `metadata.call_sid`: Twilio call SID (for status callbacks)
- `metadata.last_action_ref`: SMS/Call reference ID

### Schema: Critical Metadata Structures

#### `page_draft.metadata`

```json
{
  "status": "ready_to_publish",
  "campaign_id": "cmp_xyz",
  "keyword_id": "kw_abc123",
  "content": "<html>...</html>",
  "title": "Emergency Bail Lawyer Auckland 24/7",
  "meta_description": "...",
  "seo_score": 92,
  "has_schema": true,
  "has_form": true,
  "image_urls": ["https://..."],
  "internal_links": [{ "href": "/services", "anchor": "Services" }],
  "word_count": 1847,
  "rejection_reason": null
}
```

#### `lead.metadata`

```json
{
  "status": "scored",
  "score": 85,
  "intent": "high",
  "urgency": true,
  "source": "wordpress_form",
  "campaign_id": "cmp_leadgen_01",
  "data": {
    "name": "John Doe",
    "phone": "+64 21 123 4567",
    "email": "john@example.com",
    "message": "Arrested last night, need bail NOW"
  },
  "scorer_reasoning": "High intent (arrested), high urgency (NOW), qualified contact info",
  "bridge_threshold": 70,
  "call_sid": "CA1234567890abcdef",
  "last_action_ref": "SM9876543210fedcba"
}
```

---

## 3. Module Deep Dives (The Flows)

### 3.1 pSEO "Titanium" Pipeline

**Goal:** Generate 100+ hyper-local SEO pages from a single campaign config (e.g., "Bail Lawyers" × 50 cities × 3 keyword variants = 150 pages).

#### The Flow Diagram

```mermaid
flowchart LR
    Config["Campaign Config (DNA)"]
    Scout["Scout Agent"]
    Strategist["Strategist Agent"]
    Writer["Writer Agent"]
    Critic["Critic Agent"]
    Librarian["Librarian Agent"]
    Media["Media Agent"]
    Utility["Utility Agent"]
    Publisher["Publisher Agent"]
    WP["WordPress Site"]

    Config -->|targeting.service_focus| Scout
    Scout -->|Scrapes Google Maps| AnchorDB[(Anchor Entities)]
    AnchorDB --> Strategist
    Strategist -->|Generates Keywords| KeywordDB[(Keyword Entities)]
    KeywordDB -->|Batches of 10| Writer
    Writer -->|Generates HTML| DraftDB[(Draft Entities)]
    DraftDB --> Critic
    Critic -->|Validates Quality| DraftDB
    DraftDB -->|status=validated| Librarian
    Librarian -->|Adds Internal Links| DraftDB
    DraftDB -->|status=ready_for_media| Media
    Media -->|Fetches Unsplash Images| DraftDB
    DraftDB -->|status=ready_for_utility| Utility
    Utility -->|Injects Forms + Schema.org| DraftDB
    DraftDB -->|status=ready_to_publish| Publisher
    Publisher -->|Deploys via WP REST API| WP
```

#### Agent Roles (The "Assembly Line")

1. **Scout Agent** (Intel Gathering)

   - **Input:** `{ service_focus: "Bail", geo_targets: ["Auckland", "Hamilton"] }`
   - **Action:** Scrapes Google Maps for related places (courts, police stations, legal services).
   - **Output:** Creates `anchor_location` entities with lat/lng, address, name.
   - **Critical Logic:** De-duplicates by place ID; filters by relevance (e.g., keywords in description).

2. **Strategist Agent** (Keyword Expansion)

   - **Input:** Anchors + campaign config.
   - **Action:** Generates keyword variants (e.g., "bail lawyer auckland", "24/7 bail service manukau").
   - **Output:** Creates `seo_keyword` entities with `metadata.priority_score`.
   - **Critical Logic:** Uses LLM to expand keywords based on anchor context; ranks by search volume heuristics.

3. **Writer Agent** (Content Generation)

   - **Input:** Batch of 10 keywords (status=`pending`).
   - **Action:** Calls GPT-4 to generate full HTML page (1500-2000 words).
   - **Output:** Creates `page_draft` entities with `metadata.content` and `status=draft`.
   - **Critical Logic:**
     - Pulls RAG context from ChromaDB (competitor intel, regulations).
     - Injects brand voice from campaign DNA (`brand_brain.voice_tone`).
     - Uses keyword as H1; includes semantic variations in H2/H3.

4. **Critic Agent** (Quality Assurance)

   - **Input:** Drafts with `status=draft`.
   - **Action:** LLM Judge validates: readability, keyword density, E-E-A-T signals, duplicate content risk.
   - **Output:** Sets `status=validated` (pass) or `status=rejected` (fail with reason).
   - **Critical Logic:**
     - Rejection triggers re-write (Writer picks it up again).
     - Max 2 rejection cycles before manual review flag.

5. **Librarian Agent** (Internal Linking)

   - **Input:** Drafts with `status=validated`.
   - **Action:** Injects 3-5 internal links to existing pages (keyword-relevant anchors).
   - **Output:** Updates `metadata.internal_links` and sets `status=ready_for_media`.
   - **Critical Logic:** Uses RAG to find semantically similar existing pages; avoids over-linking (max 1 link per 300 words).

6. **Media Agent** (Image Enhancement)

   - **Input:** Drafts with `status=ready_for_media`.
   - **Action:** Fetches 2-4 relevant images from Unsplash API.
   - **Output:** Injects `<img>` tags with alt text, updates `metadata.image_urls`, sets `status=ready_for_utility`.
   - **Critical Logic:** Image selection based on keyword + location (e.g., "auckland courthouse", "lawyer office").

7. **Utility Agent** (Forms & Schema.org)

   - **Input:** Drafts with `status=ready_for_utility`.
   - **Action:**
     - Injects contact form HTML (reads `campaign.config.form_settings`).
     - Adds Schema.org LocalBusiness JSON-LD.
   - **Output:** Final HTML with forms/schema, sets `status=ready_to_publish`.
   - **Critical Logic:**
     - Form fields configured per campaign (e.g., "Name", "Phone", "Case Type").
     - Schema includes NAP (Name, Address, Phone) from project DNA.

8. **Publisher Agent** (Deployment)
   - **Input:** Drafts with `status=ready_to_publish`.
   - **Action:** Posts to WordPress via REST API (creates/updates post).
   - **Output:** Sets `status=published`, stores `metadata.wp_post_id`.
   - **Critical Logic:**
     - Idempotent: checks if post already exists (by keyword ID); updates instead of duplicates.
     - Sets post status to "publish" or "draft" based on campaign settings.

#### Budget Guards & Throttling

- **Monthly Spend Limit:** Default $50/project (configurable in DNA).
- **Abort Logic:** If `memory.get_monthly_spend(project_id) >= limit`, Manager halts Scout/Strategist/Writer (paid LLM calls).
- **Rate Limiting:** Writer batches 10 keywords at a time; waits 5s between batches to avoid API throttling.

---

### 3.2 Lead Gen "Inbound" Engine

**Goal:** Capture web leads, score intent, bridge high-value calls to client's phone in <60s, reactivate cold leads via SMS.

#### The Flow Diagram

```mermaid
sequenceDiagram
    participant Form as WordPress Form
    participant Webhook as Webhook Router
    participant Scorer as Scorer Agent
    participant Sales as Sales Bridge Agent
    participant Twilio as Twilio API
    participant Client as Client Phone
    participant Reactivator as Reactivator Agent

    Form->>Webhook: POST /webhooks/lead (data)
    Webhook->>Scorer: Create lead entity + dispatch

    Note over Scorer: LLM Judge evaluates intent/urgency
    Scorer->>Scorer: Score = 85/100 (high intent)
    Scorer->>Sales: Dispatch if score >= threshold (70)

    Sales->>Twilio: Initiate call (lead phone)
    Twilio->>Form: Call lead
    Form->>Twilio: Press 1 to connect
    Twilio->>Twilio: Bridge to client phone
    Twilio->>Client: Ring client

    alt Call Connected
        Client->>Twilio: Answer
        Twilio->>Form: Connected (lead + client)
        Note over Sales: Update lead status=connected
    else No Answer
        Twilio->>Sales: Status callback (no-answer)
        Sales->>Reactivator: Queue for SMS reactivation
        Reactivator->>Twilio: Send SMS (24h later)
        Twilio->>Form: "Hi John, saw you inquired..."
    end
```

#### Agent Roles (The "Conversion Engine")

1. **Webhook Handler** (`/webhooks/lead`)

   - **Input:** Form POST data (name, phone, email, message).
   - **Action:** Creates `lead` entity with `status=new`, metadata contains raw form data.
   - **Trigger:** Dispatches `LeadGenManager` with `action=lead_received`.

2. **Scorer Agent** (LLM Judge)

   - **Input:** Lead entity (id).
   - **Action:**
     - Builds prompt: "Score this lead: Name, Phone, Message. Rules: {scoring_rules from DNA}".
     - Calls GPT-4: Returns JSON `{ score: 0-100, intent: "high/medium/low", urgency: true/false, reasoning: "..." }`.
   - **Output:** Updates `metadata.score`, `metadata.intent`, `metadata.urgency`, sets `status=scored`.
   - **Critical Logic Gates:**
     - If `score < bridge_threshold` (default 70): skip bridge, set `status=archived`.
     - If `score >= threshold`: trigger Sales Bridge.
   - **Scoring Criteria (from DNA `scoring_rules`):**
     - **Intent Signals:** Keywords like "need", "urgent", "help", "arrested", "how much".
     - **Urgency Signals:** "now", "asap", "today", "emergency".
     - **Contact Quality:** Valid phone + email = +10 points.

3. **Sales Bridge Agent** (Instant Call)

   - **Input:** Lead entity (id) with `score >= threshold`.
   - **Action:**
     - Calls Twilio API: `client.calls.create()` with TwiML URL pointing to `/voice/connect`.
     - TwiML flow:
       1. Call lead's phone.
       2. Play whisper: "Press 1 to connect to [Business Name]".
       3. If press 1 → bridge to `campaign.config.sales_bridge.destination_phone` (client's mobile).
       4. If no press / voicemail → hang up, trigger reactivation.
   - **Output:** Stores `metadata.call_sid`, sets `status=calling`.
   - **Async Status Callback:** Twilio posts to `/voice/status` with call outcome:
     - `completed` + `duration > 30s` → `status=connected`.
     - `no-answer` / `busy` / `failed` → `status=no_answer`, queue for reactivation.

4. **Reactivator Agent** (SMS Follow-Up)
   - **Input:** Leads with `status=no_answer` or manually triggered batch (`action=ignite_reactivation`).
   - **Action:**
     - Waits 24h after first attempt (or uses campaign schedule).
     - Sends personalized SMS: "Hi [Name], saw you inquired about [Service]. Still need help? Call us: [Phone]".
   - **Output:** Updates `metadata.last_action_ref` (SMS SID), sets `status=reactivate`.
   - **Critical Logic:**
     - Max 3 SMS attempts per lead (48h apart).
     - If no response after 3rd SMS → `status=lost`.

#### Logic Gates (The "Qualification Engine")

| Condition                                 | Action                                 | Rationale                            |
| ----------------------------------------- | -------------------------------------- | ------------------------------------ |
| `score < 70`                              | Skip bridge, archive                   | Low intent = waste of Twilio credits |
| `score >= 70 && urgency=true`             | Instant bridge + priority SMS          | High intent + urgent = hot lead      |
| `score >= 70 && urgency=false`            | Instant bridge, standard reactivation  | Qualified but not urgent             |
| `call_status=no_answer`                   | Queue for SMS reactivation (24h delay) | Second touch point to re-engage      |
| `call_status=completed && duration < 10s` | Flag for review                        | Likely wrong number or hang-up       |

---

## 4. The API Surface (For Frontend Refactor)

### Required Endpoints (The "Control Panel")

#### 4.1 Entity Management

**`GET /entities?entity_type={type}&project_id={id}`**

- **Purpose:** Fetch entities with filtering and RLS enforcement.
- **Query Params:**
  - `entity_type`: Filter by type (e.g., `lead`, `page_draft`, `seo_keyword`).
  - `project_id`: Scope to project (required for non-admin users).
- **Response:**
  ```json
  {
    "entities": [
      {
        "id": "lead_abc123",
        "tenant_id": "user@example.com",
        "entity_type": "lead",
        "name": "John Doe",
        "primary_contact": "+64 21 123 4567",
        "metadata": { "status": "scored", "score": 85, ... },
        "created_at": "2026-02-01T10:30:00Z"
      }
    ]
  }
  ```
- **Frontend Use Case:**
  - Dashboard: Show lead list with scores (filter `entity_type=lead`, sort by `metadata.score`).
  - pSEO Pipeline: Show drafts by stage (filter `entity_type=page_draft`, group by `metadata.status`).

**`POST /entities`**

- **Purpose:** Create a new entity (e.g., manual lead entry, anchor override).
- **Body:**
  ```json
  {
    "entity_type": "lead",
    "name": "Manual Lead",
    "primary_contact": "+64 21 999 8888",
    "metadata": { "source": "manual", "campaign_id": "cmp_xyz" },
    "project_id": "niche_bail"
  }
  ```
- **Response:** `{ "success": true, "entity": { ... } }`

**`PUT /entities/{entity_id}`**

- **Purpose:** Update entity (e.g., mark lead as won/lost, approve draft).
- **Body:**
  ```json
  {
    "metadata": { "status": "won", "notes": "Booked appointment" }
  }
  ```
- **Frontend Use Case:**
  - Lead management: Change status dropdown (won/lost).
  - Draft review: Approve/reject button updates `metadata.status`.

**`DELETE /entities/{entity_id}`**

- **Purpose:** Soft delete entity (sets hidden flag or moves to archive).
- **Frontend Use Case:** "Delete Lead" action in lead table.

#### 4.2 Agent Dispatch (The "Command Center")

**`POST /api/run`**

- **Purpose:** Execute any agent task (synchronous or async).
- **Body:**
  ```json
  {
    "task": "pseo_manager",
    "params": {
      "action": "auto_orchestrate",
      "project_id": "niche_bail",
      "campaign_id": "cmp_abc",
      "force_continue": false
    }
  }
  ```
- **Response (Sync):**
  ```json
  {
    "status": "success",
    "data": { "stats": { ... }, "next_step": { ... } },
    "message": "Pipeline completed 15 drafts",
    "timestamp": "2026-02-01T10:30:00Z"
  }
  ```
- **Response (Async/Heavy):**
  ```json
  {
    "status": "processing",
    "data": { "context_id": "ctx_xyz123", "task": "scout_anchors" },
    "message": "Task is processing in background",
    "timestamp": "2026-02-01T10:30:00Z"
  }
  ```
- **Frontend Use Cases:**
  - "Run Scout" button → `POST /api/run` with `task=scout_anchors`.
  - "Auto-Orchestrate" button → Launches full pipeline, polls context.

**`GET /api/context/{context_id}`**

- **Purpose:** Poll status of async tasks.
- **Response:**
  ```json
  {
    "context_id": "ctx_xyz123",
    "project_id": "niche_bail",
    "user_id": "user@example.com",
    "data": {
      "status": "completed",
      "result": { "status": "success", "data": { ... }, "message": "Scout found 45 anchors" }
    },
    "created_at": "2026-02-01T10:30:00Z",
    "expires_at": "2026-02-01T11:30:00Z"
  }
  ```
- **Frontend Use Case:** Progress bar for long-running tasks (Scout, Strategist, Writer batch).

#### 4.3 Configuration & Campaigns

**`GET /api/projects/{project_id}/dna`**

- **Purpose:** Fetch merged DNA (base + custom overrides).
- **Response:**
  ```json
  {
    "config": {
      "identity": { "business_name": "Auckland Bail Services", ... },
      "brand_brain": { "voice_tone": "professional", ... },
      "modules": { "local_seo": { "enabled": true }, "lead_gen": { "enabled": true } }
    }
  }
  ```
- **Frontend Use Case:** DNA Editor (settings page).

**`PUT /api/projects/{project_id}/dna`**

- **Purpose:** Save DNA custom overrides.
- **Body:** Full or partial config object (merged with base DNA).

**`GET /api/projects/{project_id}/campaigns?module={pseo|lead_gen}`**

- **Purpose:** List campaigns for a project.
- **Response:**
  ```json
  {
    "campaigns": [
      {
        "id": "cmp_abc",
        "name": "Bail Auckland Q1 2026",
        "module": "pseo",
        "status": "ACTIVE",
        "config": { "targeting": { ... } },
        "created_at": "2026-01-15T08:00:00Z"
      }
    ]
  }
  ```

**`POST /api/projects/{project_id}/campaigns`**

- **Purpose:** Create a new campaign with config (direct, no interview).
- **Body:**
  ```json
  {
    "name": "Lead Gen - Hamilton",
    "module": "lead_gen",
    "config": {
      "targeting": { "service_focus": "Bail", "geo_targets": ["Hamilton"] },
      "sales_bridge": {
        "enabled": true,
        "destination_phone": "+64 21 555 1234"
      }
    }
  }
  ```
- **Response:** `{ "success": true, "campaign_id": "cmp_xyz", "message": "Campaign created" }`

#### 4.4 Lead Gen Specific

**`POST /voice/connect`**

- **Purpose:** Manual bridge override (admin triggers instant call to lead).
- **Body:**
  ```json
  {
    "lead_id": "lead_abc123",
    "project_id": "niche_bail"
  }
  ```
- **Response:** `{ "success": true, "call_sid": "CA123...", "message": "Call initiated" }`
- **Frontend Use Case:** "Call Now" button in lead detail view.

**`POST /api/run` (Reactivation)**

- **Body:**
  ```json
  {
    "task": "lead_gen_manager",
    "params": {
      "action": "ignite_reactivation",
      "project_id": "niche_bail",
      "campaign_id": "cmp_leadgen_01"
    }
  }
  ```
- **Frontend Use Case:** "Send SMS Batch" button in Lead Gen dashboard.

---

## 5. Market Fit & Stress Test Analysis

### The Business Model: "Rank & Rent"

**Premise:** Build 50-100 hyper-local SEO pages (e.g., "bail lawyer auckland", "bail lawyer manukau"), rank them, then rent the leads/traffic to a client at $500-$2000/month per site.

**Revenue Model:**

- **Setup Fee:** $1000-$5000 (one-time, covers initial Scout/Writer run).
- **Monthly Rent:** $500-$2000/month (per ranked site, includes lead forwarding).
- **Scaling:** 10 sites × $1000/month = $10k MRR.

### Critique 1: Does the UtilityAgent Logic Satisfy Google E-E-A-T?

**E-E-A-T = Experience, Expertise, Authoritativeness, Trustworthiness**

| E-E-A-T Factor        | Current Implementation                                                            | Gap Analysis                | Recommendation                                                 |
| --------------------- | --------------------------------------------------------------------------------- | --------------------------- | -------------------------------------------------------------- |
| **Experience**        | Writer uses RAG context (competitor analysis, regulations) to add "insider tips". | ✅ Decent signal.           | Add case study snippets from DNA (`brand_brain.insider_tips`). |
| **Expertise**         | Schema.org includes `"@type": "Attorney"` or `"LegalService"`.                    | ⚠️ Weak. No author bylines. | Inject fake "Reviewed by [Expert Name]" footer from DNA.       |
| **Authoritativeness** | Internal linking (Librarian) + external backlinks to authoritative sources.       | ✅ Solid.                   | Add 1-2 .gov or .edu outbound links per page (Writer task).    |
| **Trustworthiness**   | Contact form + NAP (Name, Address, Phone) in Schema.                              | ✅ Strong signal.           | Add SSL badge, privacy policy link (Utility task).             |

**Verdict:** Current implementation is 70% there. Missing: author attribution, stronger outbound linking, privacy/security badges.

**Fix:**

- Utility Agent: Add a "Reviewed by [DNA.identity.expert_name]" section with credentials.
- Writer Agent: Include 1-2 outbound links to `.gov` or `.edu` in each draft (e.g., "According to the New Zealand Ministry of Justice...").

### Critique 2: Is the SalesBridge Fast Enough? (Async Check)

**Speed Requirement:** Lead form submit → call initiated <60 seconds (industry standard: <2 minutes = 78% higher conversion).

**Current Flow:**

1. Form POST → Webhook (instant).
2. Create entity → dispatch Scorer (async, ~10s LLM call).
3. Scorer returns → dispatch Sales (async, ~5s Twilio call initiation).
4. Total: **~15-20 seconds** (best case).

**Bottleneck:** LLM scoring adds 10s latency.

**Optimization Paths:**

| Option                                                                         | Latency Reduction | Trade-off                           |
| ------------------------------------------------------------------------------ | ----------------- | ----------------------------------- |
| **Skip scoring for high-urgency sources** (e.g., "emergency bail" form)        | -10s              | Miss low-quality leads (spam risk)  |
| **Parallel scoring + bridge** (initiate call immediately, cancel if score low) | -10s              | Waste Twilio credits on bad leads   |
| **Pre-score form fields client-side** (JavaScript)                             | -5s               | Requires frontend logic, bypassable |
| **Use cheaper/faster LLM** (e.g., GPT-3.5-turbo)                               | -5s               | Lower quality scores                |

**Verdict:** Current 15-20s is acceptable. For ultra-speed, add a "Skip Scoring" flag in campaign config for emergency forms.

**Fix:** Add `campaign.config.sales_bridge.skip_scoring_for_urgent: true` (bypass Scorer if `source=emergency_form`).

### Critique 3: Is the System "Universal" Enough? (Forms/Scoring)

**Test Case:** Can Apex handle **non-legal niches** (e.g., HVAC, plumbing, real estate)?

| Niche              | Form Fields                                                | Scoring Logic                                           | Verdict                            |
| ------------------ | ---------------------------------------------------------- | ------------------------------------------------------- | ---------------------------------- |
| **Bail (Current)** | Name, Phone, Message, "Case Type" dropdown                 | Keywords: "arrested", "bail", "urgent"                  | ✅ Works                           |
| **HVAC**           | Name, Phone, "Issue Type" (heating/cooling), "When needed" | Keywords: "emergency", "broken", "leaking"              | ✅ Works (just change DNA)         |
| **Real Estate**    | Name, Phone, "Budget", "Looking to buy/sell", "Timeline"   | Keywords: "cash buyer", "ready to move", "pre-approved" | ⚠️ Scoring logic too bail-specific |
| **Plumbing**       | Name, Phone, "Issue", "Address"                            | Keywords: "leak", "burst pipe", "flooding"              | ✅ Works                           |

**Gap:** Scoring rules are currently tuned for **urgency-based niches** (bail, emergency services). Real estate needs **qualification-based scoring** (budget, pre-approval, timeline).

**Fix:**

- Make `campaign.config.scoring_rules` customizable per campaign (not just DNA-level).
- Add scoring rule templates in frontend (e.g., "Urgency-Based", "Qualification-Based", "Budget-Based").
- Scorer Agent: Parse `scoring_rules.criteria` JSON instead of hardcoded keywords.

**Example (Real Estate Scoring Rules):**

```json
{
  "scoring_rules": {
    "criteria": [
      { "field": "budget", "weight": 30, "condition": "> $500k", "points": 30 },
      {
        "field": "pre_approved",
        "weight": 20,
        "condition": "yes",
        "points": 20
      },
      {
        "field": "timeline",
        "weight": 15,
        "condition": "< 3 months",
        "points": 15
      },
      {
        "field": "message",
        "weight": 35,
        "keywords": ["cash", "ready", "approved"],
        "points": 35
      }
    ],
    "bridge_threshold": 60
  }
}
```

**Verdict:** System is 80% universal. Needs scoring rule templates + campaign-level overrides.

---

## 6. Deployment Architecture (Production Recommendations)

### Infrastructure Stack

```
┌─────────────────────────────────────────────────────────┐
│  Vercel (Frontend - Next.js 14)                         │
│  - Static pages + API routes for client-side polling   │
│  - CDN for global latency <50ms                         │
└───────────────┬─────────────────────────────────────────┘
                │ HTTPS
                ▼
┌─────────────────────────────────────────────────────────┐
│  Railway/Render (FastAPI Backend)                       │
│  - Single dyno/container (512MB RAM, 1 CPU)            │
│  - Gunicorn + Uvicorn workers (4 workers)              │
│  - Auto-scaling: 1-3 instances based on CPU >70%       │
└───────────────┬─────────────────────────────────────────┘
                │
    ┌───────────┴───────────┐
    ▼                       ▼
┌─────────────┐     ┌─────────────────────┐
│ PostgreSQL  │     │ ChromaDB (Persistent)│
│ (RLS)       │     │ - Mounted volume     │
│ 1GB storage │     │ - 500MB storage      │
└─────────────┘     └─────────────────────┘
```

### Cost Breakdown (First 100 Pages)

| Service           | Usage                                                             | Cost     |
| ----------------- | ----------------------------------------------------------------- | -------- |
| **OpenAI GPT-4**  | Writer (100 pages × 2000 tokens) + Scorer (50 leads × 500 tokens) | ~$15     |
| **Google Gemini** | Embeddings (1000 chunks × 768 dims)                               | ~$0.50   |
| **Twilio**        | 50 calls (10 min avg) + 100 SMS                                   | ~$50     |
| **Unsplash**      | 400 image fetches (rate-limited, free tier)                       | $0       |
| **Railway**       | 1 dyno × 730 hrs/month                                            | $5       |
| **PostgreSQL**    | Managed DB (Railway included)                                     | $0       |
| **Vercel**        | Frontend hosting (free tier)                                      | $0       |
| **Total Monthly** | (Assuming 100 pages/month + 50 leads)                             | ~**$70** |

### Scaling Limits

| Metric          | Current Capacity                             | Bottleneck                            | Fix                                   |
| --------------- | -------------------------------------------- | ------------------------------------- | ------------------------------------- |
| **Pages/Hour**  | ~10 (Writer batches of 10, 5min LLM latency) | LLM rate limits                       | Add multiple OpenAI keys, round-robin |
| **Leads/Hour**  | ~50 (Scorer + Bridge in parallel)            | Twilio concurrent calls (10)          | Upgrade Twilio plan                   |
| **Campaigns**   | Unlimited (DB-scoped, no shared state)       | ChromaDB vector search >10k docs      | Shard by campaign_id                  |
| **Users (RLS)** | ~100 users (SQLite)                          | File locking at >50 concurrent writes | Migrate to PostgreSQL                 |

---

## 7. Frontend Refactor: Critical UX Flows

### Flow 1: Campaign Creation (The "Genesis")

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend

    User->>Frontend: Click "New Campaign"
    Frontend->>User: Show wizard (Targeting, Intel, Lead Gen tabs)
    User->>Frontend: Fill form (Service, City, Bridge Phone)
    Frontend->>User: Live JSON preview updates
    User->>Frontend: Click "Launch Campaign"
    Frontend->>Backend: POST /api/projects/{id}/campaigns
    Backend->>Backend: memory.create_campaign()
    Backend->>Frontend: { campaign_id, success }
    Frontend->>User: Redirect to /dashboard
```

**Key UI Components:**

- **Split-screen layout:** Left = form tabs (Shadcn Tabs), Right = live JSON preview.
- **Validation:** Zod schema ensures `destination_phone` required if `enableCallBridge=true`.
- **Generate Test Sample:** Button triggers `/api/run` with dry-run params (not yet implemented; stub in UI).

### Flow 2: pSEO Pipeline Dashboard

**URL:** `/projects/{id}/pseo`

**Layout:**

```
┌────────────────────────────────────────────────────────┐
│  pSEO Pipeline Dashboard                               │
├────────────────────────────────────────────────────────┤
│  [Run Scout] [Run Strategist] [Auto-Orchestrate]       │
├────────────────────────────────────────────────────────┤
│  Metric Cards:                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ Anchors  │ │ Keywords │ │ Drafts   │ │ Published│ │
│  │   45     │ │   150    │ │   120    │ │    85    │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
├────────────────────────────────────────────────────────┤
│  Pipeline Stages (Table):                              │
│  ┌────────────┬────────┬─────────────────────────┐    │
│  │ Stage      │ Count  │ Action                  │    │
│  ├────────────┼────────┼─────────────────────────┤    │
│  │ Unreviewed │  15    │ [Review Drafts]         │    │
│  │ Validated  │  30    │ [Run Librarian]         │    │
│  │ Linked     │  25    │ [Run Media]             │    │
│  │ Imaged     │  20    │ [Run Utility]           │    │
│  │ Ready      │  30    │ [Publish to WordPress]  │    │
│  └────────────┴────────┴─────────────────────────┘    │
└────────────────────────────────────────────────────────┘
```

**API Calls:**

- Load stats: `POST /api/run` → `{ task: "pseo_manager", params: { action: "dashboard_stats" } }`
- Run agent: `POST /api/run` → `{ task: "scout_anchors", params: { campaign_id } }` (async)
- Poll progress: `GET /api/context/{context_id}` every 5s until `status=completed`.

### Flow 3: Lead Management (The "War Room")

**URL:** `/projects/{id}/leads`

**Layout:**

```
┌────────────────────────────────────────────────────────┐
│  Lead Gen Dashboard                                    │
├────────────────────────────────────────────────────────┤
│  [Send SMS Batch] [Export CSV] [Filter: All ▼]        │
├────────────────────────────────────────────────────────┤
│  Metric Cards:                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ Leads    │ │ Avg Score│ │ Called   │ │ Won      │ │
│  │   47     │ │   72     │ │    35    │ │    12    │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
├────────────────────────────────────────────────────────┤
│  Leads Table (TanStack Table):                        │
│  ┌────────┬──────┬────────┬──────┬──────────────┐    │
│  │ Name   │Score │ Intent │Status│ Actions      │    │
│  ├────────┼──────┼────────┼──────┼──────────────┤    │
│  │John Doe│  85  │ High   │Scored│[Call] [Won]  │    │
│  │Jane S. │  65  │ Medium │Arch. │[Reactivate]  │    │
│  │Bob W.  │  92  │ High   │Won   │[View Details]│    │
│  └────────┴──────┴────────┴──────┴──────────────┘    │
└────────────────────────────────────────────────────────┘
```

**API Calls:**

- Load leads: `GET /entities?entity_type=lead&project_id={id}`
- Manual call: `POST /voice/connect` → `{ lead_id }`
- Update status: `PUT /entities/{lead_id}` → `{ metadata: { status: "won" } }`

---

## 8. Known Limitations & Future Roadmap

### Current Limitations

1. **No Multi-Tenancy UI:** Frontend doesn't support switching between projects (uses `activeProjectId` from store, but no visual selector in all pages).

   - **Fix:** Add project dropdown in Shell header.

2. **No Webhook Testing UI:** Admin can't simulate webhook POST from frontend.

   - **Fix:** Add "Test Webhook" button in Lead Gen dashboard (sends dummy POST to `/webhooks/lead`).

3. **No Draft Preview:** User can't see generated HTML before publish.

   - **Fix:** Add "Preview" button in draft table → opens modal with iframe (render `metadata.content`).

4. **No Budget Alerts:** User doesn't know when approaching monthly spend limit.

   - **Fix:** Add budget gauge in dashboard (`GET /api/usage?project_id={id}`).

5. **No A/B Testing:** Can't test multiple form variants or scoring rules.
   - **Fix:** Add "Campaign Variants" feature (duplicate campaign, tweak config, compare conversion rates).

### Roadmap (Q1 2026)

| Feature                    | Priority | Effort | Impact                       |
| -------------------------- | -------- | ------ | ---------------------------- |
| **Draft Preview Modal**    | High     | 2 days | UX: Avoids blind publish     |
| **Budget Gauge**           | High     | 1 day  | Risk: Prevents overspend     |
| **Project Switcher**       | Medium   | 1 day  | UX: Multi-tenant support     |
| **Webhook Test UI**        | Medium   | 2 days | DX: Easier debugging         |
| **Campaign A/B Testing**   | Low      | 1 week | Growth: Optimize conversions |
| **Voice Transcription UI** | Low      | 3 days | Ops: Review call quality     |

---

## Appendix A: Agent Registry (Complete List)

| Agent Key           | Module   | Purpose                        | Heavy?                |
| ------------------- | -------- | ------------------------------ | --------------------- |
| `scout_anchors`     | pSEO     | Scrape Google Maps for anchors | Yes (external API)    |
| `strategist_run`    | pSEO     | Generate keywords from anchors | Yes (LLM batch)       |
| `write_pages`       | pSEO     | Generate HTML content          | Yes (LLM per keyword) |
| `critic_review`     | pSEO     | QA drafts (reject/approve)     | Yes (LLM batch)       |
| `librarian_link`    | pSEO     | Add internal links             | No                    |
| `enhance_media`     | pSEO     | Fetch/inject images            | No (cached API)       |
| `enhance_utility`   | pSEO     | Add forms + schema             | No                    |
| `publisher_run`     | pSEO     | Deploy to WordPress            | No (REST API)         |
| `lead_scorer`       | Lead Gen | Score lead intent              | Yes (LLM call)        |
| `sales_agent`       | Lead Gen | Bridge call via Twilio         | No (async webhook)    |
| `reactivator_agent` | Lead Gen | Send SMS follow-ups            | No (batch API)        |
| `onboarding`        | System   | Project setup wizard           | Yes (LLM interview)   |
| `health_check`      | System   | System diagnostics             | No                    |
| `janitor`           | System   | Cleanup old contexts           | No                    |

---

## Appendix B: Environment Variables (Required)

```bash
# Core
DATABASE_URL=postgresql://user:pass@localhost/apex  # Or use default SQLite
APEX_SECRET_KEY=your-secret-key-min-32-chars
APEX_CORS_ORIGINS=http://localhost:3000,https://yourdomain.com

# OpenAI (GPT-4 for Writer, Critic, Scorer)
OPENAI_API_KEY=sk-...

# Google (Gemini for embeddings)
GOOGLE_API_KEY=AIza...

# Twilio (Voice/SMS for Sales Bridge)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1234567890

# Unsplash (Images for Media Agent)
UNSPLASH_ACCESS_KEY=...

# Google Maps (Scout scraping)
GOOGLE_MAPS_API_KEY=AIza...

# WordPress (Publisher Agent)
# These are per-project, stored in DNA config (not env vars)

# Optional: Ngrok URL for local Twilio webhooks
NGROK_URL=https://abc123.ngrok.io
```

---

## Conclusion

The "Titanium" refactor has achieved:

1. ✅ **Event-Driven Kernel:** Single dispatch point, context injection, RLS enforcement.
2. ✅ **Entity-First Design:** All state in DB, no hidden pipelines.
3. ✅ **pSEO Linear Pipeline:** 8-agent assembly line (Scout → Publisher).
4. ✅ **Lead Gen Inbound Engine:** 3-agent conversion flow (Scorer → Bridge → Reactivator).
5. ✅ **Memory Abstraction:** SQL + ChromaDB with Google embeddings.

**Frontend Rebuild Goal:** Build a Linear/Vercel-style UI that exposes this architecture via the 4 core API surfaces (Entities, Dispatch, Config, Voice). Focus on UX flows for Campaign Creation, Pipeline Dashboard, and Lead Management.

**Next Steps:**

1. Implement `/campaigns/new` page (split-screen wizard) → **Done in v5 refactor**.
2. Build `/projects/{id}/pseo` dashboard (metric cards + pipeline table).
3. Build `/projects/{id}/leads` dashboard (lead table + call/SMS actions).
4. Add draft preview modal and budget gauge.

**Document Status:** Living document. Update as agents evolve or new endpoints are added.

---

_Generated by: Principal Software Architect_  
_Date: February 2, 2026_  
_Version: 1.0 (Post-Titanium)_
