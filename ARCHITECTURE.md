# Apex Vertical Operating System - Architecture Documentation

**Version:** 3.2 (Titanium Kernel + Database Abstraction)  
**Target Audience:** Senior Engineers, CTOs, System Architects  
**Purpose:** Comprehensive technical documentation for a SaaS product targeting MRR

---

## 1. System Overview

### Mission

Apex is a **Vertical Operating System** for service businesses (Plumbers, Lawyers, Locksmiths, etc.) that automates the three critical revenue functions:

1. **Lead Capture** - 24/7 automated lead generation and instant connection
2. **Client Communication** - AI-powered voice routing, transcription, and analysis
3. **SEO Dominance** - Programmatic content generation for Google Maps ranking

The system operates as an "Invisible Bridge" - connecting customers to clients instantly via AI, without requiring constant client login or manual intervention.

### Core Philosophy

**"The Invisible Bridge"** - The system eliminates friction between customer intent and client response:

- **Customer** submits a form → **System** instantly calls the **Client** → **Client** presses "1" → **Customer** is connected
- **Customer** calls Google Maps listing → **System** forwards to **Client** → **System** records, transcribes, and analyzes → **Client** receives structured data
- **System** scrapes job boards → **System** scores leads → **System** triggers bridge calls for high-value leads

The client never needs to log in. The system works in the background, routing value directly to their phone.

### Core Concepts (Titanium Execution Model)

The system uses an **Opt-Out Async** execution model. All task execution is designed for non-blocking, observable workflows.

**By default, all tasks generate a Ticket (Context ID).** When a client calls `/api/run` or a webhook triggers an agent:

1. The API creates a **Ticket** — a unique `context_id` stored in Redis with a TTL (default 1 hour).
2. Heavy tasks (e.g. `sniper_agent`, `sales_agent`, `onboarding`) are queued to **BackgroundTasks** and return immediately with `status: "processing"` and the Ticket.
3. The frontend (or webhook consumer) can **poll** `GET /api/context/{context_id}` to check status and retrieve the result when `status` is `completed` or `failed`.

**Only specific "Instant Actions" bypass the queue.** These are lightweight, sub-second operations that run synchronously and return a full result in the same HTTP response. Examples:

- `lead_gen_manager` with `action: "dashboard_stats"` — stats aggregation
- `manager` with `action: "dashboard_stats"` — pSEO stats
- `health_check` — system diagnostics
- `log_usage` — usage ledger writes

All other tasks are treated as **heavy** and go through the async path: Ticket → background worker → context updates in Redis.

**Redis "Sticky Note" System.** Redis is used as short-term, TTL-based state storage for async workflows:

- **Key pattern:** `context:{context_id}`
- **Value:** JSON-serialized context (project_id, user_id, `data` with status, result, etc.)
- **TTL:** Configurable via `REDIS_TTL_SECONDS` (default 3600). Keys expire automatically.
- **Fallback:** If Redis is unavailable, the context manager uses an in-memory dictionary (single-instance only; not suitable for multi-worker production).

This provides a single source of truth for "where is this task?" and "what was the outcome?" without blocking the API or webhooks.

### Tech Stack

| Layer              | Technology                             | Purpose                                          |
| ------------------ | -------------------------------------- | ------------------------------------------------ |
| **Backend**        | Python 3.9+, FastAPI, Uvicorn          | REST API, Agent Orchestration                    |
| **Frontend**       | Next.js 16, TypeScript, Tailwind CSS   | Dashboard, Forms, Real-time UI                   |
| **Database**       | PostgreSQL/SQLite (Relational), ChromaDB (Vector) | Database-agnostic layer; PostgreSQL for production, SQLite for dev |
| **Cache/Context**  | Redis (Optional)                       | Short-term agent context, TTL-based expiration   |
| **AI Engine**      | Google Gemini 1.5 Flash                | Transcription, Content Generation, Lead Analysis |
| **Communications** | Twilio (Voice, SMS)                    | Bridge calls, SMS alerts, call recording         |
| **Scraping**       | Playwright (Chromium)                  | Web scraping for lead generation                 |
| **Storage**        | Local filesystem (SQLite, YAML)        | Project DNA, entity storage                      |
| **Concurrency**    | FastAPI BackgroundTasks                | Async task execution for heavy operations        |

---

## 2. System Architecture

### High-Level Architecture Diagram

```mermaid
graph TB
    subgraph "External Sources"
        GA[Google Ads]
        WP[WordPress Forms]
        TM[TradeMe Jobs]
        MAPS[Google Maps]
    end

    subgraph "Entry Points"
        WH[Webhooks Router]
        VR[Voice Router]
        API[FastAPI /api/run]
    end

    subgraph "Core System"
        K[Kernel<br/>Agent Dispatcher]
        MEM[(Memory Manager<br/>PostgreSQL/SQLite + ChromaDB)]
        DBF[Database Factory<br/>PostgreSQL/SQLite Abstraction]
        DNA[DNA Config Loader]
        REDIS[(Redis<br/>Context Manager)]
        BG[BackgroundTasks<br/>Queue]
    end

    subgraph "Agent Layer"
        LG[Lead Gen Agents]
        PSEO[pSEO Agents]
        SO[System Ops Agents]
        ONB[Onboarding Agent]
    end

    subgraph "External Services"
        TWILIO[Twilio API]
        GEMINI[Google Gemini API]
        WP_API[WordPress API]
    end

    subgraph "Client & Customer"
        BOSS[Client Phone]
        CUST[Customer Phone]
    end

    GA -->|POST /webhooks/google-ads| WH
    WP -->|POST /webhooks/wordpress| WH
    TM -->|Scraped by| LG
    MAPS -->|Calls| VR

    WH -->|Creates Lead| K
    VR -->|Handles Call| K
    API -->|Agent Requests| K

    K -->|Loads Config| DNA
    K -->|Verifies Ownership| MEM
    MEM -->|Uses| DBF
    K -->|Creates Context| REDIS
    K -->|Dispatches| LG
    K -->|Dispatches| PSEO
    K -->|Dispatches| SO
    K -->|Dispatches| ONB
    K -->|Heavy Tasks| BG

    BG -->|Async Execution| LG
    BG -->|Async Execution| PSEO

    LG -->|Bridge Call| TWILIO
    LG -->|Transcribe| GEMINI
    PSEO -->|Generate Content| GEMINI
    PSEO -->|Publish| WP_API
    SO -->|Health Check| MEM
    SO -->|Usage Tracking| MEM

    TWILIO -->|Rings| BOSS
    TWILIO -->|Connects| CUST
    BOSS -.->|Presses 1| CUST

    MEM -->|Stores| LG
    MEM -->|Stores| PSEO
    MEM -->|Stores| SO
    REDIS -->|Short-term Memory| K
```

### Component Interaction Flow

```mermaid
sequenceDiagram
    participant C as Customer
    participant W as Webhook
    participant K as Kernel
    participant SA as SalesAgent
    participant T as Twilio
    participant B as Boss/Client
    participant M as Memory

    C->>W: Submits Form
    W->>K: POST /webhooks/google-ads
    K->>M: Verify Project Ownership
    M-->>K: Ownership Confirmed
    K->>M: Create Lead Entity
    M-->>K: Lead Saved
    K->>SA: Dispatch "sales_agent"
    SA->>T: Initiate Bridge Call
    T->>B: Ring Boss Phone
    B->>T: Presses "1"
    T->>C: Connect Customer
    C<->>B: Voice Conversation
    T->>W: Call Status Webhook
    W->>T: Fetch Recording
    T-->>W: Recording URL
    W->>K: Transcribe & Analyze
    K->>M: Update Lead with Analysis
```

---

## 3. Core Modules & Agents

### Module Architecture Pattern

All modules follow a consistent pattern:

```
modules/{module_name}/
├── manager.py          # Orchestrator agent (optional)
└── agents/
    ├── agent1.py       # Worker agents
    └── agent2.py
```

**Registration:** Agents are registered in `backend/core/registry.py` and dynamically loaded by the Kernel at startup.

### 3.1 Lead Gen Module (`modules/lead_gen/`)

**Purpose:** Active lead generation, instant connection, and lead nurturing.

#### LeadGenManager (Orchestrator)

- **Task:** `lead_gen_manager`
- **Actions:**
  - `hunt_sniper` - Triggers lead scraping
  - `ignite_reactivation` - SMS blast to old leads
  - `instant_call` - Bridge call for new lead
  - `transcribe_call` - Manual transcription trigger
  - `dashboard_stats` - Analytics aggregation

#### SalesAgent

**The "Speed-to-Lead" Engine**

- **Task:** `sales_agent`
- **Actions:**
  - `instant_call` - Creates bridge call (Boss ↔ Customer)
  - `notify_sms` - Sends SMS alert to boss

**Flow:**

1. Receives lead_id from webhook/manager
2. Fetches lead from database
3. Calls boss's phone with Twilio
4. Boss hears whisper: "Apex Alert. Press 1 to connect."
5. Boss presses "1" → Customer is connected
6. Call is recorded, transcribed, and analyzed

**Configuration (DNA):**

```yaml
modules:
  lead_gen:
    sales_bridge:
      destination_phone: "+6421000000" # Boss's private mobile
      whisper_text: "Apex Alert. New high-value lead on the line. Press 1 to connect."
      sms_alert_template: "🔥 HOT LEAD: [Source] - [Name]"
```

#### SniperAgent

**The "Lead Hunter"**

- **Task:** `sniper_agent`
- **Purpose:** Scrapes job boards (TradeMe, Facebook Groups) for service requests
- **Flow:**
  1. Reads keywords and geo-filters from DNA
  2. Constructs search URLs for each platform
  3. Scrapes listing pages with Playwright
  4. Uses Gemini to extract structured lead data from HTML
  5. Deduplicates against existing leads
  6. Saves new leads to database
  7. Automatically triggers scoring for new leads

**Configuration:**

```yaml
modules:
  lead_gen:
    sniper:
      enabled: true
      platforms: ["trademe_jobs", "facebook_groups"]
      keywords: ["urgent plumber", "leaking", "broken window"]
      geo_filter: ["Auckland", "Manukau"]
```

#### ReactivatorAgent

**The "Old Client Miner"**

- **Task:** `reactivator_agent`
- **Purpose:** Sends SMS campaigns to past customers to reactivate them
- **Flow:**
  1. Queries database for leads with status "won" or "completed"
  2. Filters by date (e.g., last contact > 6 months ago)
  3. Sends personalized SMS with offer
  4. Tracks responses and updates lead status

#### LeadScorerAgent

**The "Quality Filter"**

- **Task:** `lead_scorer`
- **Purpose:** Scores leads by quality using AI analysis
- **Flow:**
  1. Analyzes lead metadata (source, message, location)
  2. Uses Gemini to score: urgency, budget, fit
  3. Updates lead metadata with score (0-100)
  4. High-scoring leads trigger instant bridge calls

#### Voice Router (`routers/voice.py`)

**The "Call Handler"**

Handles all Twilio webhook callbacks:

- `/api/voice/incoming` - Inbound call forwarding
- `/api/voice/connect` - Bridge connection (boss presses "1")
- `/api/voice/status` - Call completion handler
- `/api/voice/recording-status` - Recording availability
- `/api/voice/transcription` - Transcription completion

**Key Features:**

- Automatic call recording (dual-channel)
- Transcription via Google Gemini
- Call analysis (sentiment, intent, next steps)
- Lead entity updates with call data

### 3.2 pSEO Module (`modules/pseo/`)

**Purpose:** Programmatic SEO for Google Maps dominance through automated content generation.

#### ManagerAgent (Orchestrator)

- **Task:** `manager`
- **Purpose:** Orchestrates the full pSEO pipeline
- **Pipeline:** Scout → Strategist → Writer → Critic → Librarian → Media → Publisher → Analytics

#### ScoutAgent

- **Task:** `scout_anchors`
- **Purpose:** Finds anchor locations (Courts, Police Stations, etc.) for location-based content
- **Output:** List of anchor entities with coordinates

#### StrategistAgent

- **Task:** `strategist_run`
- **Purpose:** Analyzes keywords and generates content clusters
- **Output:** Keyword matrix with primary/secondary keywords per location

#### SeoWriterAgent

- **Task:** `write_pages`
- **Purpose:** Generates HTML content based on Project DNA
- **Input:** DNA config (brand_brain, services, geo_scope)
- **Output:** SEO-optimized HTML pages with schema markup

#### CriticAgent

- **Task:** `critic_review`
- **Purpose:** Quality assurance - reviews generated content
- **Output:** Quality score + improvement suggestions

#### LibrarianAgent

- **Task:** `librarian_link`
- **Purpose:** Adds internal linking between location pages
- **Output:** Updated HTML with internal links

#### MediaAgent

- **Task:** `enhance_media`
- **Purpose:** Adds images, maps, and visual elements
- **Output:** Enhanced HTML with media

#### PublisherAgent

- **Task:** `publish`
- **Purpose:** Deploys content to WordPress/CMS
- **Configuration:** WordPress URL, credentials (encrypted in database)

#### AnalyticsAgent

- **Task:** `analytics_audit`
- **Purpose:** Analyzes performance and provides feedback
- **Output:** Performance metrics and recommendations

### 3.3 System Operations Module (`modules/system_ops/`)

**Purpose:** System health monitoring, resource usage tracking, and maintenance operations.

#### SystemOpsManager (Orchestrator)

- **Task:** `system_ops_manager`
- **Actions:**
  - `run_diagnostics` - Triggers comprehensive health check

#### SentinelAgent

**The "Health Monitor"**

- **Task:** `health_check`
- **Purpose:** Performs system-wide health diagnostics
- **Checks:**
  1. Internet connectivity (Google ping)
  2. Disk space availability (warns if < 1GB free)
  3. Twilio API connectivity
  4. Database connectivity (PostgreSQL/SQLite via DatabaseFactory)
  5. Gemini API key configuration
- **Output:** `SystemHealthStatus` with overall status and component health
- **Response Format:**
  ```json
  {
    "status": "healthy" | "critical",
    "database_ok": true,
    "twilio_ok": true,
    "gemini_ok": true,
    "disk_space_ok": true
  }
  ```

#### AccountantAgent

**The "Billing Tracker"**

- **Task:** `log_usage`
- **Purpose:** Tracks resource usage and enforces spending limits
- **Input Params:**
  - `resource`: Resource type (e.g., "twilio_voice", "gemini_token")
  - `quantity`: Quantity used (e.g., minutes, tokens)
- **Flow:**
  1. Validates project ownership
  2. Calculates cost based on resource type and quantity
  3. Logs usage to `usage_ledger` table
  4. Checks monthly spend against project limit
  5. Returns status: "ACTIVE" or "PAUSED" if limit exceeded
- **Resource Types:**
  - `twilio_voice`: $0.05 per minute
  - `gemini_token`: $0.001 per 1k tokens
- **Database:** `usage_ledger` table tracks all resource usage per project

#### JanitorAgent

**The "Cleanup Service"**

- **Task:** `cleanup`
- **Purpose:** Cleans up old files and maintains disk space
- **Operations:**
  - Deletes log files older than 30 days
  - Deletes download files older than 24 hours
  - Reports total space freed

**Configuration:**

```yaml
modules:
  system_ops:
    enabled: true
    health_check:
      disk_space_threshold_gb: 1.0
    billing:
      default_project_limit_usd: 50.0
```

### 3.4 Onboarding Module (`modules/onboarding/`)

**Purpose:** Project initialization and DNA generation.

#### OnboardingAgent

- **Task:** `onboarding`
- **System Agent:** Bypasses DNA loading (creates the DNA)
- **Flow:**
  1. Receives business information from frontend
  2. Optionally scrapes website for context
  3. Uses Gemini to generate `dna.generated.yaml`
  4. Registers project in database
  5. Saves DNA to `data/profiles/{project_id}/`
  6. Stores context in ChromaDB for RAG

---

## 4. Critical Data Flows (The "Money" Flows)

### Flow A: The "Speed-to-Lead" (Web Form → Instant Connection)

**Business Value:** Connects customer to client within 30 seconds of form submission.

**Step-by-Step:**

1. **Customer submits form** (Google Ads landing page, WordPress form)
   - Form POSTs to `/api/webhooks/google-ads?project_id={id}` or `/api/webhooks/wordpress?project_id={id}`

2. **Webhook Router validates & normalizes**
   - Validates `project_id` format (regex: `^[a-zA-Z0-9_-]+$`)
   - Verifies project ownership via `memory.get_project_owner()`
   - Normalizes payload (name, phone, email, message)

3. **Lead Entity created**
   - `Entity` saved to database with:
     - `tenant_id` = project owner
     - `entity_type` = "lead"
     - `metadata` = {source, status: "new", project_id, raw_payload}

4. **SalesAgent triggered (Async Processing)**
   - Webhook calls `/api/run` with `task: "sales_agent"`
   - Backend detects heavy task → Creates Redis context → Returns immediately:
     ```json
     {
       "status": "processing",
       "data": {
         "context_id": "uuid-here",
         "task": "sales_agent"
       },
       "message": "Task 'sales_agent' is processing in background"
     }
     ```
   - Background task executes:
     - Kernel dispatches `sales_agent` task
     - SalesAgent fetches lead from database
     - Reads `destination_phone` from DNA config

5. **Bridge call initiated**
   - Twilio calls boss's phone
   - Boss hears: "Apex Alert. New high-value lead on the line. Press 1 to connect."
   - Boss presses "1"

6. **Customer connected**
   - Twilio bridges boss ↔ customer
   - Call is recorded (dual-channel)

7. **Call completion**
   - Twilio webhook → `/api/voice/status`
   - System fetches recording
   - Transcribes with Google Gemini
   - Analyzes transcription (sentiment, intent, next steps)
   - Updates lead entity with call data
   - Updates Redis context with completion status

**Time to Connection:** < 30 seconds from form submit to voice connection.

**Key Change:** Webhook now returns HTTP 200 immediately with `status: "processing"` instead of waiting for full execution. Frontend can poll Redis context or wait for webhook callbacks for completion status.

### Flow B: The "Inbound Intelligence" (Google Maps Call → CRM Update)

**Business Value:** Every inbound call is captured, transcribed, and analyzed automatically.

**Step-by-Step:**

1. **Customer calls Google Maps listing**
   - Twilio number receives call
   - Webhook → `/api/voice/incoming?project_id={id}`

2. **Call forwarded to boss**
   - System reads `destination_phone` from DNA
   - Twilio forwards call to boss's phone
   - Call is recorded

3. **Call ends**
   - Twilio webhook → `/api/voice/status`
   - System fetches recording URL

4. **Transcription & Analysis**
   - Recording downloaded
   - Transcribed with Google Gemini (Whisper API)
   - Transcription analyzed:
     ```json
     {
       "summary": "Customer needs urgent plumbing repair",
       "key_points": ["Leaking pipe", "Weekend availability"],
       "customer_intent": "Immediate service required",
       "next_steps": ["Schedule appointment", "Send quote"],
       "sentiment": "positive",
       "urgency": "high"
     }
     ```

5. **Lead entity created/updated**
   - If new customer: Create lead entity
   - If existing: Update with call data
   - Metadata includes: `call_transcription`, `call_analysis`, `call_duration`, `recording_url`

**Result:** Every call becomes a structured CRM entry with actionable insights.

### Flow C: The "Lead Hunter" (Scraping → Scoring → Bridge)

**Business Value:** Automatically finds and connects high-value leads from job boards.

**Step-by-Step:**

1. **SniperAgent triggered**
   - Manager dispatches `hunt_sniper` action
   - Reads keywords and geo-filters from DNA

2. **Platform scraping**
   - Constructs search URLs (e.g., TradeMe Jobs)
   - Scrapes with Playwright
   - Extracts HTML content

3. **AI extraction**
   - HTML → Gemini prompt
   - Returns structured JSON:
     ```json
     [
       {
         "title": "Need a plumber",
         "url": "https://trademe.co.nz/...",
         "location": "Auckland",
         "description": "Urgent leak",
         "urgency": "High"
       }
     ]
     ```

4. **Deduplication**
   - Checks existing leads by URL
   - Skips duplicates

5. **Lead storage**
   - Creates `Entity` for each new lead
   - Metadata: `{source: "sniper", platform, keyword, location, urgency}`

6. **Automatic scoring**
   - Manager triggers `lead_scorer` for each new lead
   - Gemini analyzes lead quality
   - Updates metadata: `{score: 85}`

7. **High-value bridge call**
   - If score > 80: Triggers `instant_call` action
   - Boss receives bridge call
   - Customer connected instantly

**Result:** High-value leads are automatically identified and connected within minutes of posting.

---

## 4.5 Concurrency Model (Titanium Upgrade)

This section details the **Opt-Out Async** model introduced in **Core Concepts**. The default is async: tasks produce a **Ticket** (Context ID) and run in the background; only **Instant Actions** bypass the queue.

### Execution Paths

**Async path (default for heavy work):**

- Request hits `/api/run` or webhook-triggered flow.
- API creates a Redis **context** (Ticket), queues the task to **FastAPI BackgroundTasks**, and returns immediately with `status: "processing"` and `context_id`.
- Frontend polls `GET /api/context/{context_id}` until `data.status` is `completed` or `failed`, then reads `data.result`.
- Redis stores short-term context (TTL: 1 hour default). See **Redis "Sticky Note" System** in Core Concepts.

**Sync path (Instant Actions only):**

- Reserved for sub-second, read-heavy or simple write operations.
- No Ticket is created; the handler runs the agent synchronously and returns the full result in the same HTTP response.

### Task Classification

**Heavy tasks (async, always produce a Ticket):**

- `sniper_agent` — Lead scraping (5+ minutes)
- `sales_agent` — Bridge call setup (1+ minute)
- `reactivator_agent` — SMS campaigns (5+ minutes)
- `onboarding` — DNA generation (2+ minutes)
- Manager actions: `hunt_sniper`, `ignite_reactivation`, `instant_call` (when triggered via `lead_gen_manager`)

**Instant Actions (sync, bypass queue):**

- `manager` with `action: "dashboard_stats"` — pSEO stats aggregation
- `lead_gen_manager` with `action: "dashboard_stats"` — Lead gen stats
- `health_check` — System diagnostics
- `log_usage` — Usage ledger writes
- Other fast, non–long-running operations

### Titanium Request Flow

```mermaid
flowchart TB
    subgraph Client
        U[User / Frontend]
    end

    subgraph API["FastAPI /api/run"]
        A[Receive Request]
        A --> B{Instant Action?}
        B -->|Yes| C[Run Sync]
        B -->|No| D[Create Ticket]
        D --> E[Store in Redis]
        E --> F[Queue to BackgroundTasks]
        F --> G[Return 200 + context_id]
        C --> H[Return 200 + result]
    end

    subgraph Worker["Background Worker"]
        W[Execute Agent]
        W --> UPD[Update Redis Context]
    end

    subgraph Redis["Redis Sticky Notes"]
        R[(context:uuid)]
    end

    U -->|POST /api/run| A
    G --> U
    H --> U
    F --> W
    E --> R
    W --> UPD
    UPD --> R
```

**Flow summary:** The API classifies each request as **Instant** or **Heavy**. Instant actions run synchronously and return the result. Heavy tasks create a Ticket in Redis, enqueue work to the background worker, and return the `context_id`. The worker updates Redis on completion. The client polls `GET /api/context/{context_id}` (served by the API, which reads from Redis) until `status` is `completed` or `failed`.

### Context Management

**Redis Context (Short-term Memory):**

- **Purpose:** Track async task progress and state
- **TTL:** 3600 seconds (1 hour) default
- **Storage:** Redis (with in-memory fallback if Redis unavailable)
- **Structure:**
  ```json
  {
    "context_id": "uuid",
    "project_id": "apex-bail-manukau",
    "user_id": "user@example.com",
    "created_at": "2024-01-01T00:00:00",
    "expires_at": "2024-01-01T01:00:00",
    "data": {
      "request_id": "uuid",
      "task": "sales_agent",
      "status": "processing" | "completed" | "failed"
    }
  }
  ```

**Context Lifecycle:**

1. Created when heavy task is scheduled
2. Updated by agents during execution
3. Automatically expires after TTL
4. Can be extended via `context.extend_ttl()`

### API Response Patterns

**Synchronous Response (Light Tasks):**

```json
{
  "status": "success" | "error",
  "data": { ... },
  "message": "Task completed",
  "timestamp": "2024-01-01T00:00:00"
}
```

**Asynchronous Response (Heavy Tasks):**

```json
{
  "status": "processing",
  "data": {
    "context_id": "uuid-here",
    "task": "sniper_agent"
  },
  "message": "Task 'sniper_agent' is processing in background",
  "timestamp": "2024-01-01T00:00:00"
}
```

### Frontend Integration

**Polling Pattern:**

```typescript
// Poll context every 2 seconds until complete
const pollContext = async (contextId: string) => {
  const context = await api.get(`/api/context/${contextId}`);
  if (context.data.status === "completed") {
    return context.data.result;
  }
  // Continue polling...
};
```

**Webhook Pattern:**

- Agents can trigger webhooks on completion
- Frontend listens for webhook callbacks
- More efficient than polling

---

## 5. Database Design (The "Entity" Model)

### Database Abstraction Layer

The system uses a **database-agnostic architecture** that supports both PostgreSQL (production) and SQLite (development) through a unified `DatabaseFactory` interface.

**Location:** `backend/core/db.py`

**Key Features:**
- **Automatic Detection:** Reads `DATABASE_URL` environment variable
  - If `DATABASE_URL` is set and starts with `postgres://` or `postgresql://` → Uses PostgreSQL (psycopg2)
  - Otherwise → Falls back to SQLite (sqlite3)
- **Unified Interface:** All database operations use the factory, ensuring compatibility
- **SQL Syntax Abstraction:** Automatically converts SQL syntax differences:
  - Placeholders: `?` (SQLite) vs `%s` (PostgreSQL)
  - `INSERT OR REPLACE` → `INSERT ... ON CONFLICT ... DO UPDATE` (PostgreSQL)
  - Date functions: `date('now', 'start of month')` → `date_trunc('month', CURRENT_DATE)` (PostgreSQL)
  - Row factories: `sqlite3.Row` vs `psycopg2.extras.RealDictRow`
- **Connection Management:** Context managers ensure proper cleanup and transaction handling

**Usage:**
```python
from backend.core.db import get_db_factory

db_factory = get_db_factory(db_path="data/apex.db")  # Only used for SQLite
with db_factory.get_cursor() as cursor:
    cursor.execute(f"SELECT * FROM users WHERE user_id = {db_factory.get_placeholder()}", (user_id,))
```

### Universal Entity Architecture

The system uses a **flexible, schema-less entity model** that accommodates diverse data types without schema changes.

#### Core Table: `entities`

**SQLite:**
```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,              -- UUID
    tenant_id TEXT NOT NULL,           -- User ID (RLS)
    project_id TEXT,                   -- Project ID (optional)
    entity_type TEXT NOT NULL,         -- "lead", "keyword", "page", etc.
    name TEXT NOT NULL,                -- Display name
    primary_contact TEXT,               -- Phone, email, or URL
    metadata TEXT,                      -- JSON stored as TEXT
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**PostgreSQL:**
```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,              -- UUID
    tenant_id TEXT NOT NULL,           -- User ID (RLS)
    project_id TEXT,                   -- Project ID (optional)
    entity_type TEXT NOT NULL,         -- "lead", "keyword", "page", etc.
    name TEXT NOT NULL,                -- Display name
    primary_contact TEXT,               -- Phone, email, or URL
    metadata JSONB,                     -- JSONB for efficient JSON operations
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Note:** The `DatabaseFactory` automatically uses the appropriate column type (`TEXT` for SQLite, `JSONB` for PostgreSQL) when creating tables.

#### Why This Works

**1. Multi-Tenant Isolation**

- `tenant_id` = User ID (Row-Level Security)
- All queries filtered by `tenant_id`
- Prevents cross-tenant data leaks

**2. Project Scoping**

- `project_id` = Business/Client
- One user can have multiple projects
- Entities can be project-scoped or global

**3. Type Flexibility**

- `entity_type` = "lead", "keyword", "page", "tender", etc.
- Same table structure for all types
- Type-specific logic in application layer

**4. Schema Evolution**

- `metadata` JSON column stores type-specific data
- No migrations needed for new fields
- Example metadata structures:

**Lead Entity:**

```json
{
  "source": "google_ads",
  "status": "called",
  "score": 85,
  "call_sid": "CA123...",
  "call_transcription": "...",
  "call_analysis": {
    "sentiment": "positive",
    "urgency": "high"
  },
  "project_id": "apex-bail-manukau"
}
```

**Keyword Entity:**

```json
{
  "primary_keyword": "bail lawyer",
  "location": "Manukau",
  "search_volume": 1200,
  "competition": "medium",
  "anchor_entity": "Manukau District Court"
}
```

**Page Entity:**

```json
{
  "url": "https://example.com/bail-lawyer-manukau",
  "status": "published",
  "word_count": 1200,
  "schema_type": "LegalService"
}
```

#### Additional Tables

**`users`**

- User accounts with hashed passwords
- JWT token validation

**`projects`**

- Project registry
- Links `user_id` → `project_id`
- Stores DNA path

**`client_secrets`**

- Encrypted WordPress credentials
- Uses `security_core` (Fernet encryption)

**`usage_ledger`**

- Resource usage tracking for billing
- Structure:
  ```sql
  CREATE TABLE usage_ledger (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL,
      resource_type TEXT NOT NULL,  -- "twilio_voice", "gemini_token"
      quantity REAL NOT NULL,        -- Minutes, tokens, etc.
      cost_usd REAL NOT NULL,
      timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```
- Indexed on `(project_id, timestamp)` for monthly spend queries

### Vector Storage (ChromaDB)

**Collection:** `apex_context`

**Purpose:** RAG (Retrieval-Augmented Generation) for brand brain knowledge

**Embeddings:** Google `text-embedding-004`

**Metadata:**

```json
{
  "tenant_id": "user@example.com",
  "project_id": "apex-bail-manukau",
  "type": "insider_tip",
  "source": "dna.generated.yaml"
}
```

**Usage:**

- Stores "insider tips" from DNA
- Stores "key differentiators"
- Agents query for context-aware content generation

---

## 6. Infrastructure & Configuration

### Project DNA System

**Location:** `data/profiles/{project_id}/`

**Files:**

- `dna.generated.yaml` - AI-generated (read-only, created by OnboardingAgent)
- `dna.custom.yaml` - User overrides (merged on top)

**Loading:** `ConfigLoader.load(project_id)` merges: Defaults → Generated → Custom

**Structure:**

```yaml
# LAYER 1: IDENTITY
identity:
  project_id: "apex-bail-manukau"
  business_name: "Manukau Urgent Bail"
  niche: "Criminal Defense"
  contact:
    phone: "+6421000000"
    email: "info@example.com"
    address: "Auckland, New Zealand"

# LAYER 2: BRAND BRAIN
brand_brain:
  voice_tone: "Professional, Urgent, Authoritative"
  key_differentiators: ["24/7 Availability", "Former Police Prosecutor"]
  insider_tips: ["Never speak to police without a lawyer"]
  common_objections: ["Why do I need a lawyer for a first offense?"]
  forbidden_topics: ["Guaranteed outcomes", "Illegal advice"]

# LAYER 3: SERVICES
services:
  - name: "Emergency Bail Support"
    slug: "bail"
    primary_keywords: ["bail lawyer", "urgent bail application"]
    context_keywords: ["weekend court lawyer", "emergency legal help"]

# LAYER 4: MODULES
modules:
  lead_gen:
    enabled: true
    sales_bridge:
      destination_phone: "+6421000000"
      whisper_text: "Apex Alert. New high-value lead on the line. Press 1 to connect."
    sniper:
      enabled: true
      platforms: ["trademe_jobs"]
      keywords: ["urgent plumber"]
      geo_filter: ["Auckland"]
  local_seo:
    enabled: true
    scout_settings:
      anchor_entities: ["Court", "Police Station"]
      geo_scope:
        cities: ["Auckland"]
        suburbs: ["Manukau"]
```

**Why YAML?**

- Human-readable for debugging
- Version-controllable
- Easy to merge (generated + custom)
- No database migrations needed

### Environment Variables

**Critical Keys:**

```bash
# AI
GOOGLE_API_KEY=your_gemini_api_key

# Communications
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_PHONE_NUMBER=+6421000000

# Database (Production)
DATABASE_URL=postgresql://user:password@host:port/database  # PostgreSQL for production
# If DATABASE_URL not set, falls back to SQLite (development)

# Security
APEX_JWT_SECRET=your_jwt_secret
APEX_KMS_KEY=your_fernet_key  # For encrypting secrets

# Infrastructure
NGROK_URL=https://your-ngrok-url.ngrok.io  # Local dev
NEXT_PUBLIC_API_URL=https://api.yourapp.com  # Production
DEFAULT_PROJECT_ID=apex-bail-manukau  # Fallback project
```

### The Tunnel (Ngrok)

**Purpose:** Expose local backend to Twilio webhooks during development

**Flow:**

1. Local backend runs on `localhost:8000`
2. Ngrok creates tunnel: `https://abc123.ngrok.io → localhost:8000`
3. Twilio webhooks point to `https://abc123.ngrok.io/api/voice/*`
4. Production: Use `NEXT_PUBLIC_API_URL` instead

**Why Needed:**

- Twilio requires HTTPS for webhooks
- Local development doesn't have SSL
- Ngrok provides temporary HTTPS tunnel

---

## 7. Stress Testing & MRR Readiness

### Current State: Prototype → Enterprise Grade

The system is **production-ready for MVP** but requires enhancements for **enterprise scale** (100+ clients, $10K+ MRR).

### 7.1 Security Enhancements

#### ✅ Implemented

- JWT authentication
- Project ownership verification
- Input validation (project_id regex)
- Encrypted secrets storage
- Row-level security (tenant_id)

#### ⚠️ Required for Enterprise

**1. Webhook Signature Validation**

**Current:** Webhooks accept any POST request  
**Required:** Validate Twilio signature

```python
# backend/routers/voice.py
from twilio.request_validator import RequestValidator

validator = RequestValidator(os.getenv("TWILIO_AUTH_TOKEN"))

@voice_router.post("/incoming")
async def handle_incoming_call(request: Request):
    # Validate signature
    signature = request.headers.get("X-Twilio-Signature")
    if not validator.validate(request.url, request.form(), signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    # ... rest of handler
```

**2. API Key Authentication for Frontend**

**Current:** JWT tokens only  
**Required:** API keys for programmatic access

```python
# backend/core/auth.py
def verify_api_key(api_key: str) -> Optional[str]:
    # Check API key in database
    # Return user_id if valid
    pass
```

**3. Rate Limiting**

**Current:** No rate limiting  
**Required:** Per-user, per-endpoint limits

```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@webhook_router.post("/google-ads")
@limiter.limit("10/minute")
async def handle_google_ads_webhook(...):
    pass
```

### 7.2 Multi-Tenancy Hardening

#### ✅ Implemented

- `tenant_id` filtering in all queries
- Project ownership verification
- Project_id format validation

#### ⚠️ Required for Enterprise

**1. Database-Level RLS**

**Current:** Application-level filtering  
**Required:** PostgreSQL Row-Level Security

```sql
-- PostgreSQL RLS Policy
CREATE POLICY tenant_isolation ON entities
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id')::text);
```

**2. Cross-Project Data Leak Prevention**

**Current:** Verified in application layer  
**Required:** Database constraints

```sql
-- Ensure project_id belongs to tenant_id
ALTER TABLE entities
ADD CONSTRAINT fk_project_tenant
FOREIGN KEY (project_id, tenant_id)
REFERENCES projects(project_id, user_id);
```

**3. Audit Logging**

**Current:** Application logs only  
**Required:** Structured audit trail

```python
# backend/core/audit.py
def log_audit_event(user_id: str, action: str, resource: str, details: dict):
    # Store in audit_log table
    # Include: timestamp, user_id, IP, action, resource, details
    pass
```

### 7.3 Reliability Enhancements

#### ⚠️ Required for Enterprise

**1. Retry Logic for AI Failures**

**Current:** Single attempt, fails on error  
**Required:** Exponential backoff retry

```python
# backend/core/services/llm_gateway.py
import tenacity

@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=2, max=10)
)
def generate_content(self, ...):
    # Retry on API errors
    pass
```

**2. Transaction Safety**

**Current:** No transactions for multi-step operations  
**Required:** Database transactions

```python
# backend/core/memory.py
def save_entity_with_audit(self, entity, audit_event):
    with self.conn.transaction():
        self.save_entity(entity)
        self.log_audit(audit_event)
```

**3. Dead Letter Queue**

**Current:** Failed webhooks are lost  
**Required:** Retry queue for failed operations

```python
# backend/core/queue.py
def enqueue_retry(task, max_retries=3):
    # Store in retry_queue table
    # Background worker processes queue
    pass
```

### 7.4 Scaling Considerations

#### Database Migration: SQLite → PostgreSQL

**Status:** ✅ **COMPLETED** - Database abstraction layer implemented

The system now supports both SQLite (development) and PostgreSQL (production) through a unified `DatabaseFactory` interface. Migration is automatic based on the `DATABASE_URL` environment variable.

**How It Works:**

1. **Development (SQLite):**
   - No `DATABASE_URL` set → Uses SQLite
   - Database file: `data/apex.db`
   - No additional setup required

2. **Production (PostgreSQL):**
   - Set `DATABASE_URL=postgresql://user:password@host:port/database`
   - System automatically detects and uses PostgreSQL
   - All SQL queries are converted to PostgreSQL syntax

**Trigger Points for PostgreSQL:**

1. **Concurrent Writes > 10**
   - SQLite locks on writes
   - PostgreSQL handles concurrent writes

2. **Database Size > 10GB**
   - SQLite performance degrades
   - PostgreSQL optimized for large datasets

3. **Multi-Server Deployment**
   - SQLite is file-based (single server)
   - PostgreSQL supports replication

4. **Production Deployment**
   - Managed databases (Supabase, Railway Postgres, Neon)
   - Better reliability and backup options

**Implementation:**

```python
# backend/core/db.py
class DatabaseFactory:
    def __init__(self, db_path: Optional[str] = None):
        database_url = os.getenv("DATABASE_URL", "").strip()
        if database_url.startswith(("postgres://", "postgresql://")):
            self.db_type = "postgresql"  # Uses psycopg2
        else:
            self.db_type = "sqlite"      # Uses sqlite3
```

**Migration Steps:**

1. Set up PostgreSQL database (Supabase, Railway, etc.)
2. Set `DATABASE_URL` environment variable
3. Run schema creation (tables are created automatically on first connection)
4. Migrate data if needed (use `pg_dump` / `pg_restore` or custom migration script)

#### When to Add Caching

**Trigger:** API response time > 500ms

**Solution:** Redis cache for:

- DNA configs (rarely change)
- User sessions
- Frequently queried entities

#### When to Add Message Queue

**Trigger:** Webhook processing time > 5 seconds

**Solution:** Celery + Redis for:

- Long-running tasks (scraping, transcription)
- Background processing
- Scheduled jobs (reactivation campaigns)

### 7.5 Monitoring & Observability

#### Required for Enterprise

**1. Application Performance Monitoring (APM)**

- **Tool:** Sentry, Datadog, or New Relic
- **Metrics:** Response time, error rate, throughput
- **Alerts:** Error rate > 1%, response time > 2s

**2. Structured Logging**

**Current:** Basic Python logging  
**Required:** JSON logs with correlation IDs

```python
# backend/core/logger.py
import structlog

logger = structlog.get_logger()
logger.info("agent_started", agent="sales_agent", request_id=request_id, user_id=user_id)
```

**3. Health Checks**

```python
# backend/main.py
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": check_database(),
        "chromadb": check_chromadb(),
        "twilio": check_twilio(),
        "gemini": check_gemini()
    }
```

### 7.6 Cost Optimization

#### Current Costs (Per Client/Month)

- **Google Gemini API:** ~$5-20 (depending on usage)
- **Twilio:** ~$10-50 (calls + SMS)
- **Hosting:** ~$20-50 (VPS/Heroku)

**Total:** ~$35-120/client/month

#### Optimization Strategies

1. **AI Model Selection**
   - Use Gemini Flash for non-critical tasks
   - Use Gemini Pro only for content generation

2. **Caching**
   - Cache DNA configs (rarely change)
   - Cache transcription results

3. **Batch Processing**
   - Batch lead scoring (10 at a time)
   - Schedule scraping during off-peak hours

---

## 8. Deployment Architecture

### Recommended Production Setup

```
┌─────────────────┐
│   Cloudflare    │  (CDN, DDoS Protection)
└────────┬────────┘
         │
┌────────▼────────┐
│   Next.js App   │  (Vercel/Netlify)
│   (Frontend)    │
└────────┬────────┘
         │
┌────────▼────────┐
│   FastAPI App   │  (Railway/Heroku/DigitalOcean)
│   (Backend)     │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼────┐
│SQLite │ │ChromaDB│
│(File) │ │(File) │
└───────┘ └───────┘
```

### Environment-Specific Configurations

**Development:**

- SQLite (local file, `data/apex.db`)
- Ngrok tunnel for webhooks
- Local ChromaDB
- No `DATABASE_URL` required

**Production:**

- PostgreSQL (managed database via `DATABASE_URL`)
- Public API URL
- Persistent ChromaDB volume
- Database abstraction layer handles SQL syntax differences automatically

---

## 9. Phase 4: Production & DevOps

This section defines the **production deployment architecture** and **CI/CD pipeline** for the Titanium kernel. It serves as the single source of truth for deployable infrastructure and release workflows.

### Deployment Architecture

**Stack overview**

| Layer                | Technology                           | Notes                                                                           |
| -------------------- | ------------------------------------ | ------------------------------------------------------------------------------- |
| **Frontend**         | Vercel (Next.js Edge Network)        | Serverless, global CDN, automatic HTTPS                                         |
| **Backend**          | Railway or Render (Python container) | FastAPI + Uvicorn; horizontal scaling                                           |
| **Database**         | PostgreSQL (Production) / SQLite (Dev) | Database-agnostic layer; auto-detects via `DATABASE_URL`; managed instance (e.g. Railway Postgres, Supabase, Neon) |
| **Memory / Context** | Cloud Redis                          | Migrating from local Redis; managed Redis (e.g. Upstash, Railway Redis)         |

**Data flow**

- **Frontend:** Next.js app on Vercel. Calls backend via `NEXT_PUBLIC_API_URL`. No direct DB access.
- **Backend:** Python container on Railway/Render. Connects to PostgreSQL and Redis via env vars. Exposes `/api/*`, `/health`, webhooks.
- **Database:** PostgreSQL (production) or SQLite (development) holds users, projects, entities, `usage_ledger`, etc. The `DatabaseFactory` automatically selects the appropriate database based on `DATABASE_URL`.
- **Redis:** Stores Titanium context (Tickets). Replaces in-memory fallback for multi-worker and production reliability.

**Environment variables (production)**

- `APEX_JWT_SECRET`, `APEX_KMS_KEY` — **required**; no defaults.
- `DATABASE_URL` — PostgreSQL connection string.
- `REDIS_URL` — Cloud Redis connection string.
- `GOOGLE_API_KEY`, `TWILIO_*`, `NEXT_PUBLIC_API_URL` — as per existing config.

### CI/CD Pipeline

**Workflow: Feature branch, no direct pushes to `main`**

1. All changes are developed on **feature branches** (e.g. `feature/xyz`, `fix/abc`).
2. **No direct pushes to `main`.** Updates reach `main` only via **Pull Requests**.
3. On **PR**:
   - GitHub Actions runs the **unit test suite** (e.g. `pytest backend/tests/`).
   - PR must be approved and tests must pass before merge.
4. On **merge to `main`**:
   - GitHub Actions runs tests again (optional but recommended).
   - **Auto-deploy to production:** Frontend → Vercel; Backend → Railway/Render. Deploys are triggered by merge to `main`.

**CI/CD pipeline (overview)**

```mermaid
flowchart LR
    subgraph Local
        CODE[Local Code]
        BR[Feature Branch]
        CODE --> BR
    end

    subgraph GitHub
        PR[Pull Request]
        TESTS[GitHub Actions: Unit Tests]
        MERGE[Merge to main]
        DEPLOY[Auto-Deploy]
        BR --> PR
        PR --> TESTS
        TESTS -->|Pass| MERGE
        MERGE --> DEPLOY
    end

    subgraph Production
        VERCEL[Vercel: Frontend]
        RAILWAY[Railway / Render: Backend]
        DEPLOY --> VERCEL
        DEPLOY --> RAILWAY
    end
```

**Implementing the pipeline**

- **Tests:** Add a GitHub Actions workflow (e.g. `.github/workflows/test.yml`) that runs `pytest backend/tests/` on PR and on push to `main`.
- **Vercel:** Connect the repo to Vercel; set production branch to `main`. Vercel auto-deploys on merge.
- **Railway/Render:** Connect the repo; set root to backend or use a Dockerfile. Configure build and start commands, and env vars. Auto-deploy on `main` (or on successful CI if integrated).

### Migration Notes (SQLite → PostgreSQL, Local Redis → Cloud Redis)

- **Database:** ✅ **COMPLETED** - Database abstraction layer implemented in `backend/core/db.py`. The system automatically detects PostgreSQL via `DATABASE_URL` and handles SQL syntax differences. To migrate:
  1. Set up PostgreSQL database (Supabase, Railway Postgres, Neon, etc.)
  2. Set `DATABASE_URL=postgresql://user:password@host:port/database` environment variable
  3. Tables are created automatically on first connection via `MemoryManager._init_database()`
  4. For data migration, use `pg_dump` / `pg_restore` or custom migration scripts
- **Redis:** Point `REDIS_URL` to the managed Redis instance. Ensure encryption (TLS) and authentication. No application logic change beyond configuration.

---

## 10. Future Enhancements

### Phase 2: Enterprise Features

1. **Multi-User Projects**
   - Team collaboration
   - Role-based access control

2. **Advanced Analytics**
   - Revenue attribution
   - Conversion funnel analysis
   - ROI reporting

3. **CRM Integrations**
   - HubSpot sync
   - Salesforce sync
   - Custom webhooks

4. **White-Label**
   - Custom branding
   - Client-facing dashboards

### Phase 3: AI Enhancements

1. **Predictive Lead Scoring**
   - ML model for lead quality
   - Historical conversion data

2. **Automated Follow-Ups**
   - Email sequences
   - SMS drip campaigns

3. **Voice AI Assistant**
   - Automated call handling
   - Appointment scheduling

---

## Conclusion

The Apex Vertical Operating System is architected for **scalability, security, and simplicity**. The agent-based architecture allows for modular growth, while the universal entity model provides flexibility without schema migrations.

**Current Status:** Production-ready for MVP (10-50 clients)  
**Enterprise Ready:** After implementing security, reliability, and monitoring enhancements outlined in Section 7.

**Key Strengths:**

- ✅ Flexible entity model (no schema migrations)
- ✅ Multi-tenant isolation (tenant_id RLS)
- ✅ Agent-based architecture (easy to extend)
- ✅ DNA configuration system (per-client customization)

**Next Steps for MRR Growth:**

1. Implement webhook signature validation
2. Add rate limiting
3. Set up monitoring (APM, structured logging)
4. Execute Phase 4 (Section 9): Production stack (Vercel, Railway/Render, PostgreSQL, Cloud Redis) and CI/CD
5. Add retry logic for AI operations

---

**Document Version:** 3.2  
**Last Updated:** January 2026  
**Maintained By:** Engineering Team

**Recent Updates:**
- ✅ Database abstraction layer implemented (`backend/core/db.py`)
- ✅ PostgreSQL support added (auto-detects via `DATABASE_URL`)
- ✅ SQL syntax differences automatically handled
- ✅ All database operations now use unified `DatabaseFactory` interface
