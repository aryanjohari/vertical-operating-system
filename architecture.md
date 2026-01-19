# Apex Sovereign OS - Architecture Documentation v2.0

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Overview](#architecture-overview)
3. [File Structure & Component Details](#file-structure--component-details)
4. [Core Processes & Workflows](#core-processes--workflows)
5. [User Experience](#user-experience)
6. [Data Flow](#data-flow)
7. [Key Concepts](#key-concepts)
8. [Technology Stack](#technology-stack)

---

## System Overview

**Apex Sovereign OS** (also called "Apex OS" or "Vertical Operating System") is a business automation platform designed for revenue generation and client management. The system follows a **Domain-Driven Modular Architecture** where specialized business modules contain their own agents and workflows, enabling clean separation of concerns and scalable growth.

### Core Philosophy

- **Domain-Driven Modules**: Business capabilities organized into modules (pSEO, Lead Gen, Onboarding)
- **Project-Aware Intelligence**: All agents operate within project context for multi-client isolation
- **Profile-Driven**: Each client has a unique "DNA profile" (YAML configuration) per project
- **Smart Platform**: Agents read from RAG memory before writing to ensure accuracy and context-awareness
- **Zero-to-Automation**: Onboarding process goes from website scraping → gap analysis → AI-powered interview → configuration generation

---

## Architecture Overview

The system is built on a **Domain-Driven Modular Architecture** with clear separation between business modules and shared infrastructure:

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND LAYER                        │
│  ┌─────────────────────┐  ┌─────────────────────┐     │
│  │  Streamlit UI       │  │  Next.js 14 App     │     │
│  │  (dashboard.py)     │  │  Router (TypeScript)│     │
│  │  - Onboarding       │  │  - Mission Control  │     │
│  │  - Genesis Chat     │  │  - Asset Database   │     │
│  └─────────────────────┘  │  - Agent Console    │     │
│                            └─────────────────────┘     │
└──────────────────┬──────────────────────────────────────┘
                   │ HTTP/REST
┌──────────────────▼──────────────────────────────────────┐
│                    API LAYER                             │
│              (FastAPI - backend/main.py)                 │
│  - Single Entry Point: /api/run                         │
│  - Universal Packet Routing                             │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│                  KERNEL LAYER                            │
│              (backend/core/kernel.py)                    │
│  - Agent Registry & Dispatch                            │
│  - Task Routing Logic                                   │
│  - Project-Aware Profile Loading                        │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│              DOMAIN MODULES LAYER                        │
│                                                          │
│  ┌──────────────────────────────────────────────┐      │
│  │     MODULE: APEX GROWTH (pSEO)               │      │
│  │  ┌──────────────┐  ┌──────────────────────┐ │      │
│  │  │   Manager    │  │     Worker Agents    │ │      │
│  │  │  (Strategist)│  │  ┌────────────────┐  │ │      │
│  │  │              │  │  │ Scout          │  │ │      │
│  │  │  Project-    │  │  │ SeoKeyword     │  │ │      │
│  │  │  Aware       │  │  │ SeoWriter      │  │ │      │
│  │  │  Orchestrator│  │  │ Media          │  │ │      │
│  │  │              │  │  │ Publisher      │  │ │      │
│  │  └──────┬───────┘  └──────────────────────┘ │      │
│  └─────────┼────────────────────────────────────┘      │
│            │                                            │
│  ┌─────────┼────────────────────────────────────────┐  │
│  │ ┌───────▼─────────────────────────────────────┐  │  │
│  │ │  MODULE: APEX CONNECT (Lead Gen)            │  │  │
│  │ │  ┌──────────────┐  ┌──────────────┐        │  │  │
│  │ │  │   Utility    │  │    Twilio    │        │  │  │
│  │ │  │   Agent      │  │    Agent     │        │  │  │
│  │ │  │  (Tools)     │  │  (Voice)     │        │  │  │
│  │ │  └──────────────┘  └──────────────┘        │  │  │
│  │ └──────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────┐      │
│  │     MODULE: ONBOARDING                       │      │
│  │  ┌────────────────────────────────────────┐  │      │
│  │  │   Genesis Agent                        │  │      │
│  │  │   (LangGraph State Machine)            │  │      │
│  │  │   - Scrape → Gap Analysis →            │  │      │
│  │  │     Interview → Generate               │  │      │
│  │  └────────────────────────────────────────┘  │      │
│  └──────────────────────────────────────────────┘      │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│              SHARED SERVICES LAYER                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Scraper    │  │     SMS      │  │    Other     │  │
│  │   Service    │  │   Service    │  │   Services   │  │
│  │ (Playwright) │  │  (Twilio)    │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│              INFRASTRUCTURE LAYER                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Memory     │  │    Config    │  │   Logging    │  │
│  │  Manager     │  │   Loader     │  │   System     │  │
│  │ (SQL+Vector) │  │              │  │              │  │
│  │ Project-Scoped│  │              │  │              │  │
│  │ RAG Memory   │  │              │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## File Structure & Component Details

### Backend (`/backend`)

#### Core System (`/backend/core/`)

**`kernel.py`** - The Central Dispatcher

- **Purpose**: Main orchestrator that routes tasks to appropriate agents within domain modules
- **Key Functions**:
  - `register_agent()`: Dynamically loads and registers agents from modules
  - `dispatch()`: Routes incoming tasks based on task type and profile requirements
- **Routing Logic**:
  - **Bypass Rule**: System tasks like `onboarding`, `scrape_site`, and `manager` don't require profiles
  - **Standard Rule**: Profile-based tasks require loading client profiles first
  - **Smart Context Loading**: If `niche` not provided, automatically looks up user's active project from database
  - **Project-Aware Routing**: All agents receive project context automatically
  - **Task Routing**:
    - `scout_anchors`, `find` → `scout` agent (pSEO module)
    - `seo_keyword`, `keyword` → `seo_keyword` agent (pSEO module)
    - `write_pages`, `write` → `seo_writer` agent (pSEO module)
    - `enhance_media` → `media` agent (pSEO module)
    - `enhance_utility` → `utility` agent (Lead Gen module)
    - `publish` → `publisher` agent (pSEO module)
- **Registered Agents**: Loaded from `registry.py` which maps to domain modules

**`agent_base.py`** - Abstract Base Class

- **Purpose**: Defines the interface all agents must implement
- **Architecture**: Template method pattern with automatic logging wrapper
- **Key Methods**:
  - `run(input_data: AgentInput) -> AgentOutput`: Concrete wrapper method with automatic logging
    - Logs "Agent Started" at beginning
    - Logs "Agent Finished" at end with status
    - Wraps `_execute()` in try/except for error handling
    - Returns error `AgentOutput` on exceptions with full traceback
  - `_execute(input_data: AgentInput) -> AgentOutput`: Abstract method that agents implement (actual business logic)
  - `log()`: Logging utility (wrapper for `logger.info()`)
- **Logging**: All agents automatically inherit structured logging via `self.logger` (configured in `logger.py`)

**`logger.py`** - Centralized Logging System

- **Purpose**: Production-grade logging configuration with color-coded console output and file rotation
- **Features**:
  - **Console Handler**: Color-coded output using ANSI codes
    - Green for INFO
    - Yellow for WARNING
    - Red for ERROR
    - Blue for DEBUG
  - **File Handler**: Rotating file handler (`logs/apex.log`)
    - Max file size: 10MB
    - Backup count: 5 (keeps last 5 log files)
  - **Format**: `[YYYY-MM-DD HH:MM:SS] [LEVEL] [COMPONENT] : Message`
- **Configuration**:
  - `setup_logging()`: Initializes root logger with both handlers
  - Called at application startup (in `main.py`)
  - Logger hierarchy: `Apex.*` inherits from root configuration
- **Logger Instances**: Each agent gets logger via `logging.getLogger(f"Apex.{name}")`

**`models.py`** - Data Models

- **AgentInput**: Universal input packet
  - `task`: Task identifier (e.g., "onboarding", "scrape_site")
  - `user_id`: User identifier (for RLS/permissions)
  - `params`: Flexible dictionary for task-specific parameters (includes `project_id` for project-aware operations)
  - `request_id`: UUID for request tracking
- **AgentOutput**: Universal response packet
  - `status`: "success", "error", "continue", "complete", "action_required"
  - `data`: Result payload (can be any type)
  - `message`: Human-readable summary
  - `timestamp`: Request timestamp
- **Entity**: Database record format
  - `id`: Unique identifier (UUID or hash-based)
  - `tenant_id`: User ID for RLS (links to `users.user_id`)
  - `project_id`: Optional project identifier for project-scoped data
  - `entity_type`: Type of entity (see below)
  - `name`: Display name/title
  - `primary_contact`: Email, phone, or URL
  - `metadata`: Flexible JSON dictionary for type-specific data
  - `created_at`: Timestamp (datetime object)
  - **Entity Types & Metadata**: Same as v1.4 (anchor_location, seo_keyword, page_draft, lead, etc.)

**`memory.py`** - Dual-Memory System with Project-Scoped RAG

- **Purpose**: Manages both structured (SQL) and semantic (vector) storage with strict RLS and project-scoping
- **Components**:
  - **SQLite** (`apex.db`): Structured data storage with Row-Level Security (RLS) and Project Filtering
    - **System Tables**:
      - `users`: User authentication (user_id as email, password)
      - `projects`: Links users to their DNA profiles (project_id, user_id, niche, dna_path, created_at)
      - `client_secrets`: Per-user WordPress credentials (user_id, wp_url, wp_user, wp_password)
    - **Data Tables**:
      - `entities`: Master table for all data entities (id, tenant_id, project_id, entity_type, name, primary_contact, metadata JSON, created_at)
        - `project_id`: Required for project-scoped queries (nullable for backward compatibility)
      - `logs`: Audit trail for system actions (id, tenant_id, action, details, timestamp)
    - **RLS Enforcement**: All queries filtered by `tenant_id` (user_id) for data isolation
    - **Project Filtering**: Entities can be filtered by `project_id` for project-specific views
  - **ChromaDB** (`chroma_db/`): Vector embeddings for semantic search with Project-Scoped RAG
    - Collection: `apex_knowledge` (renamed from `apex_context` for clarity)
    - **Project-Scoped Storage**: All context stored with `project_id` in metadata
    - Used for context retrieval, strategy docs, email templates, legal references
    - **RLS + Project Scoping**: Metadata filtering by both `tenant_id` AND `project_id`
- **Key Methods**:
  - **Authentication & Projects**:
    - `create_user(email, password)`: Register new user
    - `verify_user(email, password)`: Validate user credentials
    - `register_project(user_id, project_id, niche)`: Link DNA profile to user
    - `get_user_project(user_id)`: Retrieve user's active project/niche from database
    - `get_projects(user_id)`: Retrieve all projects for a user
  - **Entity Management** (Project-Aware):
    - `save_entity(entity: Entity, project_id: Optional[str] = None)`: Save structured records with project scoping
    - `get_entities(tenant_id, entity_type=None, project_id=None)`: Retrieve entities with RLS + project filtering
      - **Project Filtering**: Returns entities matching project OR with NULL project_id (backward compatibility)
    - `update_entity(entity_id, new_metadata)`: Update metadata of existing entities
  - **Client Credentials**:
    - `save_client_secrets(user_id, wp_url, wp_user, wp_password)`: Save or update WordPress credentials
    - `get_client_secrets(user_id)`: Retrieve WordPress credentials for a user
  - **Semantic Memory (Project-Scoped RAG)**:
    - `save_context(tenant_id, text, metadata, project_id=None)`: Store text embeddings in ChromaDB with project_id
    - `query_context(tenant_id, query, n_results=3, project_id=None)`: Semantic search with RLS + project filtering
      - **RAG Memory Loop**: Agents query this before writing content to cite accurate information (e.g., legal references)

**`config.py`** - Profile Loader

- **Purpose**: Loads and merges client configuration profiles (project-aware)
- **Merge Strategy** (in order of priority):
  1. System defaults (currency, timezone)
  2. Generated DNA (`dna.generated.yaml`) - AI-created config
  3. Custom overrides (`dna.custom.yaml`) - Human overrides (highest priority)
- **Location**: Profiles stored in `data/profiles/{project_id}/`
- **Project Context**: Loads profile based on `project_id` from active project

**`registry.py`** - Module Catalog & Agent Directory

- **Purpose**: Defines available modules/capabilities and maps agent keys to their module locations
- **Agent Directory**: Maps agent keys to module paths and class names
  ```python
  DIRECTORY = {
      "onboarding": ("backend.modules.onboarding.genesis", "OnboardingAgent"),
      "manager": ("backend.modules.pseo.manager", "ManagerAgent"),
      "scout": ("backend.modules.pseo.agents.scout", "ScoutAgent"),
      "seo_keyword": ("backend.modules.pseo.agents.keyword", "SeoKeywordAgent"),
      "seo_writer": ("backend.modules.pseo.agents.writer", "SeoWriterAgent"),
      "media": ("backend.modules.pseo.agents.media", "MediaAgent"),
      "publisher": ("backend.modules.pseo.agents.publisher", "PublisherAgent"),
      "utility": ("backend.modules.lead_gen.agents.utility", "UtilityAgent"),
      "twilio": ("backend.modules.lead_gen.agents.twilio", "TwilioAgent"),
  }
  ```
- **Module Manifest**: Defines business modules (app store catalog)
  - `local_seo` → "Apex Growth (pSEO)": Local SEO automation
  - `lead_gen` → "Apex Connect (Lead Gen)": 24/7 Lead Capture & Voice Routing
- **Key Methods**:
  - `get_user_menu()`: Returns module list for UI checkboxes
  - `get_config_rules()`: Returns required config fields per module

**`profile_template.yaml`** - Master Configuration Template

- **Purpose**: Schema for client profiles (same as v1.4)
- **Sections**:
  1. **Identity**: Business name, contact info, niche, project_id
  2. **Scout Rules**: Lead generation parameters (geo scope, keywords, anchor entities)
  3. **Content DNA**: Brand voice, pain points, pSEO strategy
  4. **Operations**: Voice settings, limits, automation flags

#### Domain Modules (`/backend/modules/`)

The system is organized into **business domain modules**, each containing related agents and workflows:

##### **Module: APEX GROWTH (pSEO)** (`/backend/modules/pseo/`)

**Purpose**: Automates local SEO content production through a 5-phase pipeline.

**Structure**:
- `manager.py`: The Strategist/Orchestrator (project-aware manager)
- `agents/`:
  - `scout.py`: Anchor location scouting agent
  - `keyword.py`: SEO keyword generation agent
  - `writer.py`: SEO content writing agent
  - `media.py`: Media enhancement agent
  - `publisher.py`: Content publishing agent

**`manager.py`** - The Strategist (Project-Aware Orchestrator)

- **Purpose**: Orchestrates the complete 5-phase pSEO production pipeline **within a specific project context**
- **Project-Aware Behavior**:
  - Filters all entity queries by `project_id` to ensure data isolation
  - Loads project-specific DNA profile to generate search queries
  - Returns stats and directives scoped to the current project
- **Process**:
  1. Retrieves user's active project from database
  2. Loads project-specific DNA profile
  3. Queries entities filtered by `project_id`: `memory.get_entities(tenant_id, entity_type, project_id)`
  4. Analyzes pipeline state (counts anchors, keywords, pages for that project only)
  5. Determines next action based on project's current phase
  6. Returns `action_required` status with next task to execute, or `complete` when all done
- **5-Phase Pipeline**:
  1. **Phase 1: Scout** - Find anchor locations (courts, prisons, etc.) for the project
  2. **Phase 2: Keywords** - Generate SEO keywords from locations (project-scoped)
  3. **Phase 3: Writing** - Create HTML landing page drafts (project-specific)
  4. **Phase 4a: Media** - Add images to pages
  5. **Phase 4b: Utility** - Add interactive tools/widgets (via Lead Gen module)
  6. **Phase 5: Publishing** - Push to WordPress/Vercel
- **Returns**: `action_required` status with next task to execute, or `complete` when all done
- **Stats Tracking**: Monitors counts of anchors, keywords, drafts, enhanced pages, etc. **for the current project only**

**`agents/scout.py`** - Lead Scouting Agent

- **Purpose**: Multi-mode agent for website scraping and location-based lead generation
- **Modes**:
  1. **System Mode** (`scrape_site`): Scrapes websites without profile (used in onboarding)
  2. **Anchor Location Scouting** (`scout_anchors`): Profile-based Google Maps scraping for anchor entities
     - Uses profile's `scout_rules` configuration (geo_scope, allow_keywords, block_keywords, anchor_entities)
     - Scrapes Google Maps for locations matching the criteria
     - Saves results as `anchor_location` entities with `project_id`
- **Tools**: Uses `backend/core/services/universal.py` and `backend/core/services/maps_sync.py`

**`agents/keyword.py`** - SEO Keyword Generation Agent

- **Purpose**: Generates high-intent SEO keywords based on anchor locations
- **Process**:
  1. Fetches `anchor_location` entities filtered by `project_id`
  2. Uses Gemini AI to generate keyword templates (e.g., "{name} Bail Accommodation in {city}")
  3. Applies templates to each anchor location to create unique keywords
  4. Saves keywords as `seo_keyword` entities with `project_id` and status "pending"
- **Project-Aware**: Only processes keywords for the current project

**`agents/writer.py`** - SEO Content Writer Agent

- **Purpose**: Generates high-converting HTML landing pages from SEO keywords
- **RAG Memory Loop**: **Queries `apex_knowledge` vector DB before writing** to cite accurate legal references, local laws, etc.
- **Process**:
  1. Fetches pending `seo_keyword` entities filtered by `project_id`
  2. **Queries RAG memory** (`memory.query_context()`) with project-specific context to retrieve relevant knowledge
  3. Uses Gemini AI with system instructions + RAG context to write 600-word HTML pages
  4. Includes: H1, intro, USPs, process, service details, FAQs, CTA
  5. Generates Schema.org JSON-LD (LocalBusiness)
  6. Creates internal links to related pages in same city (project-scoped)
  7. Saves as `page_draft` entities with `project_id`
  8. Updates keyword status to "published"
- **Features**:
  - **Context-Aware Content**: Cites specific laws, regulations from RAG memory
  - Internal linking (connects related pages in same city within project)
  - Structured data (Schema.org markup)
  - Mentions target anchor and city 3x for SEO

**`agents/media.py`** - Media Enhancement Agent

- **Purpose**: Adds visual elements to page drafts using Unsplash API
- **Process**:
  1. Fetches `page_draft` entities without images, filtered by `project_id`
  2. Searches Unsplash for relevant images (query: city + "justice building")
  3. Injects image HTML at top of page content
  4. Updates page metadata with `image_url` and prepends image to content
- **Batch Processing**: Processes up to 5 pages at a time

**`agents/publisher.py`** - Content Publishing Agent

- **Purpose**: Publishes completed page drafts to CMS (WordPress or Vercel)
- **Process**:
  1. Fetches WordPress credentials from database using `memory.get_client_secrets(user_id)`
  2. Returns error if credentials not found for user
  3. Fetches `page_draft` entities with `has_tool: True` and status not "published"/"live", filtered by `project_id`
  4. Publishes to configured target (WordPress or GitHub/Vercel)
  5. Updates page metadata: `status: "published"` on success
- **Project-Aware**: Only publishes pages for the current project

##### **Module: APEX CONNECT (Lead Gen)** (`/backend/modules/lead_gen/`)

**Purpose**: Handles lead capture and communication automation.

**Structure**:
- `agents/`:
  - `utility.py`: Interactive tool builder agent
  - `twilio.py`: Twilio voice/webhook handler agent

**`agents/utility.py`** - Interactive Tool Builder Agent

- **Purpose**: Adds JavaScript interactive tools/widgets to pages (lead magnets)
- **Process**:
  1. Fetches `page_draft` entities with images but no tools, filtered by `project_id`
  2. Determines tool type based on keyword (e.g., "Bail" → Bail Cost Estimator)
  3. Uses Gemini AI to generate HTML/JS widget code with lead capture
  4. Injects tool before FAQs section
  5. Updates page metadata with `has_tool: True`
- **Tool Types**:
  - Bail Cost Estimator (for "bail" keywords)
  - Legal Aid Eligibility Quiz (for "aid" keywords)
  - Simple Contact Form (default)
- **Lead Capture**: Tools POST form data to `/api/leads` endpoint with `project_id`
- **Batch Processing**: Processes up to 5 pages at a time

**`agents/twilio.py`** - Twilio Voice Agent

- **Purpose**: Handles voice call routing and lead capture from Twilio webhooks
- **Process**: Processes incoming calls, forwards to configured numbers, captures call recordings as leads
- **Project-Aware**: Uses `project_id` from webhook to load project config and save leads with project context

##### **Module: ONBOARDING** (`/backend/modules/onboarding/`)

**Purpose**: AI-powered client profile generation through graph-based state machine.

**Structure**:
- `genesis.py`: Onboarding Agent (LangGraph State Machine)

**`genesis.py`** - Genesis Agent (Graph-Based Onboarding)

- **Purpose**: AI-powered consultant that creates client profiles through a structured state machine
- **Graph-Based Workflow**:
  1. **Scrape Phase**: Website scraping via shared scraper service
  2. **Gap Analysis Phase**: Analyzes scraped data to identify missing information
  3. **Interview Phase**: Interactive AI conversation to fill gaps and configure modules
  4. **Generate Phase**: Creates YAML profile matching `profile_template.yaml`
    - **Process**:
  1. Receives scraped website data + selected modules
  2. Uses Gemini AI with LangGraph state machine to guide conversation
  3. Asks module-specific configuration questions based on selected modules
  4. Generates YAML profile with project_id
  5. Saves to `data/profiles/{project_id}/dna.generated.yaml`
- **AI Model**: `gemini-2.5-flash` (Google Genai)
- **State Machine**: Tracks conversation state, ensures all required fields are captured before generation

#### Shared Services (`/backend/core/services/`)

**Purpose**: "Dumb Tools" - stateless utility services used by agents across modules.

**`universal.py`** - Web Scraper Service

- **Purpose**: Universal website scraper using Playwright
- **Features**:
  - Headless browser automation
  - Extracts title and body text
  - Handles JavaScript-heavy sites
  - Returns structured data: `{url, title, content, error}`
- **Technology**: Playwright (Chromium)

**`maps_sync.py`** - Google Maps Scraper Service

- **Purpose**: Synchronous Google Maps scraper for location-based data collection
- **Function**: `run_scout_sync(queries, allow_kws, block_kws)`
- **Features**:
  - Scrapes Google Maps search results (New Zealand maps: `google.co.nz/maps`)
  - Handles both list results and single results
  - Infinite scroll detection for list results
  - Keyword filtering (allow/block keywords)
  - Extracts: name, address, phone, website, Google Maps URL
  - Deduplication based on name + address
- **Technology**: Playwright (synchronous mode)

**Future Services**:
- `sms_service.py`: Twilio SMS service (for lead dispatch)
- Additional utility services as needed

#### Routers (`/backend/routers/`)

**`voice.py`** - Twilio Voice Webhook Handler

- **Purpose**: Handles incoming voice calls and call status callbacks from Twilio
- **Endpoints**:
  - `POST /api/voice/incoming`: Incoming call webhook
    - Extracts `project_id` from query/form data
    - Loads project config to get `forwarding_number`
    - Returns TwiML `<Dial>` response
  - `POST /api/voice/status`: Call status callback
    - Extracts call info and recording URL
    - Creates lead entity with `recording_url` in metadata
    - Saves to database with `project_id`

#### API (`/backend/`)

**`main.py`** - FastAPI Application

- **Purpose**: REST API entry point
- **Initialization**: Calls `setup_logging()` from `backend.core.logger` at startup
- **Endpoints**:
  - `GET /`: Health check, returns loaded agents
  - `POST /api/run`: Main execution endpoint (accepts `AgentInput`, returns `AgentOutput`)
  - `GET /api/entities`: Entity retrieval (supports `project_id` filtering)
  - `POST /api/leads`: Lead capture endpoint (accepts `project_id`)
  - `GET /api/projects`: Get all projects for user
  - `POST /api/projects`: Create new project and trigger onboarding
  - `POST /api/auth/verify`: User authentication

#### Scripts (`/scripts/`)

**`add_client.py`** - Client Credential Setup Script

- **Purpose**: Helper script for manually adding WordPress credentials for clients
- **Usage**: `python scripts/add_client.py`

### Frontend (`/frontend/`)

#### **Streamlit Dashboard** (`dashboard.py`)

- **Purpose**: Onboarding and initial setup interface
- **Technology**: Streamlit (Python-based UI)
- **Graph-Based Onboarding Flow**:
  1. **Phase 1 (Init)**: Website URL input → Scraper Service scrapes site
  2. **Phase 2 (Modules)**: Module selection (app store) → User selects capabilities
  3. **Phase 3 (Chat)**: Genesis chat → Graph-based AI consultant creates profile

#### **Next.js 14 App Router** (Modern React/TypeScript Frontend)

- **Purpose**: Professional dashboard for operations and monitoring
- **Features**:
  - **Mission Control** (`/dashboard`): Project-scoped stats and directives
  - **Asset Database** (`/dashboard/assets`): View entities by type (project-filtered)
  - **Agent Console** (`/dashboard/console`): Terminal interface for agent execution
  - **Leads Management** (`/dashboard/leads`): Project-filtered leads with audio playback
- **Project Management**:
  - Project selector in sidebar (localStorage-backed context)
  - All stats and data auto-refresh to show current project only

### Data (`/data/`)

**`apex.db`** - SQLite Database

- **5-Table Schema**: `users`, `projects`, `entities`, `logs`, `client_secrets`
- **Project-Scoped Entities**: All entities link to projects via `project_id`
- **RLS Enforced**: All queries filtered by `tenant_id` for data isolation

**`chroma_db/`** - ChromaDB Vector Database

- **Collection**: `apex_knowledge` (project-scoped RAG)
- **Purpose**: Semantic embeddings for context retrieval with project isolation
- **Project Scoping**: All context stored with `project_id` in metadata

**`profiles/`** - Client Configuration Profiles

- **Structure**: `data/profiles/{project_id}/`
- **Files**: `dna.generated.yaml`, `dna.custom.yaml` (optional)

---

## Core Processes & Workflows

### 1. Complete pSEO Production Pipeline (Manager-Driven, Project-Aware)

```
User Selects Project in Frontend
    │
    ▼
User Clicks "Run Strategy"
    │
    ▼
POST /api/run {task: "manager", user_id, params: {project_id}}
    │
    ▼
┌─────────────────────────┐
│  Manager Agent          │
│  (Project-Aware)        │
│  - Loads project DNA    │
│  - Filters entities by  │
│    project_id           │
│  - Analyzes pipeline    │
│    state for project    │
└────────┬────────────────┘
         │
         ├─ Phase 1: No Anchors?
         │  └─→ Task: "scout_anchors"
         │       └─→ Scout Agent → Maps Scraper
         │            └─→ Creates anchor_location entities (with project_id)
         │
         ├─ Phase 2: Few Keywords?
         │  └─→ Task: "seo_keyword"
         │       └─→ SeoKeyword Agent → Gemini AI
         │            └─→ Creates seo_keyword entities (with project_id)
         │
         ├─ Phase 3: No Drafts?
         │  └─→ Task: "write_pages"
         │       └─→ SeoWriter Agent → RAG Memory → Gemini AI
         │            └─→ Queries apex_knowledge (project-scoped)
         │            └─→ Creates page_draft entities (with project_id)
         │
         ├─ Phase 4a: Drafts Need Images?
         │  └─→ Task: "enhance_media"
         │       └─→ Media Agent → Unsplash API
         │
         ├─ Phase 4b: Images Need Tools?
         │  └─→ Task: "enhance_utility"
         │       └─→ Utility Agent → Gemini AI
         │
         └─ Phase 5: Ready to Publish?
            └─→ Task: "publish"
                 └─→ Publisher Agent → WordPress/Vercel
```

### 2. Onboarding Workflow (Graph-Based State Machine)

```
User Input (Website URL)
    │
    ▼
┌─────────────────┐
│  Phase 1: Scrape│
│  (Universal     │
│   Scraper)      │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  Phase 2: Gap Analysis  │
│  - Analyzes scraped data│
│  - Identifies missing   │
│    information          │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Phase 3: Interview     │
│  (LangGraph State       │
│   Machine)              │
│  - Interactive AI chat  │
│  - Module-specific Q&A  │
│  - Tracks conversation  │
│    state                │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Phase 4: Generate      │
│  - Creates YAML profile │
│  - Saves to             │
│    data/profiles/       │
│    {project_id}/        │
│    dna.generated.yaml   │
└─────────────────────────┘
```

### 3. RAG Memory Loop (Context-Aware Content Generation)

```
SeoWriter Agent Starts
    │
    ▼
┌─────────────────────────┐
│  Queries RAG Memory     │
│  memory.query_context(  │
│    tenant_id,           │
│    query="legal laws",  │
│    project_id           │
│  )                      │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  ChromaDB Returns       │
│  Relevant Context       │
│  (Project-Scoped)       │
│  - Legal references     │
│  - Local regulations    │
│  - Competitor analysis  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Gemini AI Writes       │
│  Content with Citations │
│  - Mentions specific    │
│    laws/regulations     │
│  - Accurate references  │
│  - Context-aware copy   │
└─────────────────────────┘
```

---

## User Experience

### Frontend View: Mission Control

**Project Selection Flow**:

1. **User logs in** → Frontend loads user's projects from `GET /api/projects`
2. **User selects project** from sidebar dropdown → Project context stored in localStorage
3. **Dashboard auto-refreshes** → All stats show **only** that project's data:
   - Locations Found (for selected project)
   - Keywords Generated (for selected project)
   - Pages Written (for selected project)
   - Leads Captured (for selected project)

**Action: User Clicks "Run Strategy"**:

1. Next.js sends `POST /api/run`:
   ```json
   {
     "task": "manager",
     "user_id": "admin@admin.com",
     "params": {
       "project_id": "bail_v1"
     }
   }
   ```

2. **Backend Reaction**:
   - Kernel routes to `backend/modules/pseo/manager.py`
   - Manager loads project DNA: `data/profiles/bail_v1/dna.generated.yaml`
   - Manager queries entities: `memory.get_entities(user_id, project_id="bail_v1")`
   - Manager analyzes **only** bail_v1's pipeline state
   - Returns next action: `{status: "action_required", next_task: "scout_anchors", ...}`

3. **Frontend Display**:
   - Shows directive: "Phase 1: Location Scouting"
   - Shows button: "Launch Scout"
   - User clicks → Executes `scout_anchors` task for that project

**Multi-Project Isolation**:

- Each project operates independently
- Switching projects changes entire dashboard context
- Manager agent only sees data for selected project
- All entity queries filtered by `project_id`

---

## Data Flow

### Request Flow with Project Context

```
Client (Frontend/API)
    ↓ HTTP POST
FastAPI (/api/run)
    ↓ AgentInput (with project_id in params)
Kernel (dispatch)
    ↓ Project-Aware Routing
    ↓ Load Project DNA
Agent (run method)
    ↓ Business Logic
    ↓ Query Memory (with project_id filter)
Tools (Scrapers, Memory, etc.)
    ↓ Results (project-scoped)
Agent (AgentOutput)
    ↓ Return
Kernel → FastAPI → Client
```

### RAG Memory Loop (Project-Scoped)

```
Agent Needs Context
    ↓
memory.query_context(
    tenant_id="admin@admin.com",
    query="bail laws in New Zealand",
    project_id="bail_v1"
)
    ↓
ChromaDB Query
    ↓ Filter: tenant_id + project_id
    ↓ Semantic Search
    ↓
Returns Relevant Documents
    ↓
Agent Uses Context in AI Prompt
    ↓
Content Generated with Citations
    ↓
Agent Saves Entity (with project_id)
```

### Configuration Flow (Project-Aware)

```
Profile Request (with project_id)
    ↓
ConfigLoader.load(project_id)
    ↓
Load: data/profiles/{project_id}/
    ↓
Merge Strategy:
  1. System Defaults
  2. dna.generated.yaml (AI-generated)
  3. dna.custom.yaml (Human overrides)
    ↓
Merged Config Object
    ↓
Agent receives config (project-scoped)
```

---

## Key Concepts

### 1. Domain-Driven Modular Architecture

- **Modules**: Business capabilities organized by domain (pSEO, Lead Gen, Onboarding)
- **Shared Services**: Stateless utilities used across modules
- **Clear Boundaries**: Each module owns its agents and workflows
- **Registry System**: Central catalog maps agent keys to module locations

### 2. Project-Aware Intelligence

- **Project Context**: All operations scoped to a specific `project_id`
- **Data Isolation**: Entities filtered by `project_id` for multi-client support
- **Profile Per Project**: Each project has its own DNA configuration
- **Manager Orchestration**: Manager agent operates within project boundaries

### 3. Project-Scoped RAG Memory

- **Vector Storage**: ChromaDB collection `apex_knowledge` with project metadata
- **Dual Filtering**: RLS (`tenant_id`) + Project Scoping (`project_id`)
- **Context Retrieval**: Agents query RAG before writing to cite accurate information
- **Memory Loop**: Read from RAG → Write content → Save to entities (with project_id)

### 4. Graph-Based Onboarding

- **State Machine**: LangGraph manages conversation flow
- **Phases**: Scrape → Gap Analysis → Interview → Generate
- **Module-Aware**: Questions adapt based on selected modules
- **Profile Generation**: Outputs project-specific YAML configuration

### 5. Universal Packet System

- **AgentInput**: Standard input format (includes `params.project_id` for project context)
- **AgentOutput**: Standard output format with status, data, message
- **Task Routing**: Kernel routes to appropriate module agent based on task type

### 6. Row-Level Security (RLS) + Project Filtering

- **RLS Enforcement**: All queries filtered by `tenant_id` (user_id)
- **Project Filtering**: Entities additionally filtered by `project_id`
- **ChromaDB**: Metadata filtering by both `tenant_id` AND `project_id`
- **Backward Compatibility**: NULL `project_id` handled gracefully

---

## Technology Stack

### Backend

- **Framework**: FastAPI (async REST API)
- **ASGI Server**: Uvicorn
- **Validation**: Pydantic (data models)

### AI/ML

- **LLM**: Google Gemini (via `google-genai`)
- **State Machines**: LangGraph (for onboarding)
- **Embeddings**: ChromaDB (built-in, project-scoped)

### Data Storage

- **Structured**: SQLite (`sqlite3`) with RLS + project filtering
- **Vector**: ChromaDB (local persistent, project-scoped RAG)
- **ORM**: SQLAlchemy (optional, not fully utilized)

### Web Automation

- **Scraping**: Playwright (Chromium) - shared services

### Frontend

- **Onboarding UI**: Streamlit (Python-based, `dashboard.py`)
- **Operations Dashboard**: Next.js 14 App Router (TypeScript/React)
  - Tailwind CSS styling
  - SWR for real-time data fetching
  - Shadcn/UI component library

### Configuration

- **YAML**: PyYAML
- **Environment**: python-dotenv

### Logging

- **System**: Python `logging` module with custom formatters
- **Console**: Color-coded output (ANSI codes)
- **File**: Rotating file handler to `logs/apex.log`

---

## Version History

### v2.0 - Domain-Driven Modular Architecture

- **Modular Structure**: Reorganized agents into domain modules (`pseo/`, `lead_gen/`, `onboarding/`)
- **Shared Services**: Extracted scrapers to `core/services/` as stateless utilities
- **Project-Aware Manager**: Manager agent filters all operations by `project_id`
- **Project-Scoped RAG**: ChromaDB collection renamed to `apex_knowledge` with project metadata
- **Graph-Based Onboarding**: LangGraph state machine for structured profile generation
- **RAG Memory Loop**: Agents query vector DB before writing to ensure accuracy
- **Clear Module Boundaries**: Growth Module (pSEO) and Connect Module (Lead Gen) separation

### v1.4 - Project Management & Voice Integration

- Project-based data organization
- Voice router for Twilio integration
- Project selector in frontend

### v1.3 - Production Logging & Multi-Client Support

- Centralized logging system
- Multi-client credential storage

---

**Last Updated**: Based on Domain-Driven Modular Architecture v2.0  
**Version**: 2.0  
**Maintainer**: Apex OS Development Team