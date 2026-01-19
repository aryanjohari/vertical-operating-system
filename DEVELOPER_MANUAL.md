# Apex Sovereign OS - Developer Manual

**Version**: 1.3  
**Last Updated**: 2026-01-16  
**Target Stack**: Cloud-Native (Supabase + Railway + Vercel)

---

## 📋 Table of Contents

1. [System Architecture](#system-architecture)
2. [Entity Schema (Postgres)](#entity-schema-postgres)
3. [The Engine: ManagerAgent Logic](#the-engine-manageragent-logic)
4. [Deployment Guide](#deployment-guide)
5. [Lead Capture Integration](#lead-capture-integration)
6. [Debugging Handbook](#debugging-handbook)
7. [API Reference](#api-reference)

---

## System Architecture

### Cloud-Native Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER LAYER                              │
│  ┌──────────────────┐  ┌──────────────────┐                   │
│  │  Client Website  │  │  Next.js Admin   │                   │
│  │  (WordPress)     │  │  Dashboard       │                   │
│  │  - Embedded Form │  │  - Mission Ctrl │                   │
│  │  - Lead Capture  │  │  - Asset DB     │                   │
│  └────────┬─────────┘  └────────┬─────────┘                   │
└───────────┼─────────────────────┼───────────────────────────────┘
            │                     │
            │ POST /api/leads     │ POST /api/run
            │                     │
┌───────────▼─────────────────────▼───────────────────────────────┐
│                    RAILWAY API LAYER                             │
│              (FastAPI on Railway.app)                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  FastAPI Application (backend/main.py)                    │  │
│  │  - CORS enabled for Vercel frontend                       │  │
│  │  - Single entry point: POST /api/run                      │  │
│  │  - Lead capture: POST /api/leads                          │  │
│  │  - Entity retrieval: GET /api/entities                     │  │
│  └──────────────┬───────────────────────────────────────────┘  │
│                 │                                                │
│  ┌──────────────▼───────────────────────────────────────────┐  │
│  │  Kernel (backend/core/kernel.py)                          │  │
│  │  - Task routing & agent dispatch                          │  │
│  │  - Profile loading (from Supabase Storage)                 │  │
│  └──────────────┬───────────────────────────────────────────┘  │
│                 │                                                │
│  ┌──────────────▼───────────────────────────────────────────┐  │
│  │  Agent Layer (8 Specialized Agents)                       │  │
│  │  - ManagerAgent (orchestrator)                            │  │
│  │  - ScoutAgent, SeoKeywordAgent, SeoWriterAgent, etc.     │  │
│  └──────────────┬───────────────────────────────────────────┘  │
└─────────────────┼──────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────────┐
│                    SUPABASE DATABASE                            │
│              (PostgreSQL + Storage)                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Tables:                                                  │  │
│  │  - users (auth)                                           │  │
│  │  - projects (user → profile linkage)                      │  │
│  │  - entities (leads, locations, keywords, pages)           │  │
│  │  - client_secrets (WordPress credentials)                │  │
│  │  - logs (audit trail)                                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Storage Bucket:                                         │  │
│  │  - profiles/ (YAML DNA files)                            │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                             │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │  Twilio API      │  │  Unsplash API    │                    │
│  │  - SMS Notify    │  │  - Image Search  │                    │
│  │  - Lead Alerts   │  │  - Media Assets  │                    │
│  └──────────────────┘  └──────────────────┘                    │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │  WordPress REST  │  │  Google Gemini   │                    │
│  │  - Publish Pages │  │  - AI Content    │                    │
│  └──────────────────┘  └──────────────────┘                    │
└──────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

**Next.js Frontend (Vercel)**:
- Admin dashboard for operations monitoring
- Mission Control (ManagerAgent status)
- Asset Database (view entities)
- Agent Console (trigger agents manually)

**Railway API (FastAPI)**:
- Single entry point: `/api/run` (agent execution)
- Lead capture: `/api/leads` (from client websites)
- Entity retrieval: `/api/entities` (for dashboard)
- Authentication: `/api/auth/verify`

**Supabase (PostgreSQL)**:
- All structured data (entities, users, projects, credentials)
- Row-Level Security (RLS) enforced at database level
- Storage bucket for YAML profile files

**External Services**:
- **Twilio**: SMS notifications for new leads (future)
- **Unsplash**: Image search for page enhancement
- **WordPress**: Content publishing destination
- **Google Gemini**: AI content generation

---

## Entity Schema (Postgres)

### Database Tables

All tables use **Row-Level Security (RLS)** with `tenant_id` (user_id) as the isolation key.

#### 1. `users` Table

```sql
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,  -- Email address
    password TEXT NOT NULL,    -- Hashed password (use bcrypt in production)
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Purpose**: Authentication and user management.

#### 2. `projects` Table

```sql
CREATE TABLE projects (
    project_id TEXT PRIMARY KEY,           -- e.g., 'bail_v1'
    user_id TEXT NOT NULL,                 -- FK to users.user_id
    niche TEXT,                            -- Display name
    dna_path TEXT,                        -- Path in Supabase Storage: 'profiles/{project_id}/dna.generated.yaml'
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_projects_user_id ON projects(user_id);
```

**Purpose**: Links users to their DNA profiles stored in Supabase Storage.

**Example Row**:
```json
{
  "project_id": "bail_v1",
  "user_id": "admin@admin.com",
  "niche": "Specialist Support Services (SSS)",
  "dna_path": "profiles/bail_v1/dna.generated.yaml",
  "created_at": "2026-01-16T01:05:20Z"
}
```

#### 3. `entities` Table (The Master Data Table)

```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,                  -- UUID or hash-based ID
    tenant_id TEXT NOT NULL,              -- FK to users.user_id (RLS key)
    entity_type TEXT NOT NULL,            -- 'anchor_location', 'seo_keyword', 'page_draft', 'lead'
    name TEXT NOT NULL,                   -- Display name/title
    primary_contact TEXT,                 -- Email, phone, or URL
    metadata JSONB NOT NULL DEFAULT '{}', -- Flexible JSON structure (type-specific)
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY(tenant_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_entities_tenant_id ON entities(tenant_id);
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_tenant_type ON entities(tenant_id, entity_type);
```

**Purpose**: Stores all business data (locations, keywords, pages, leads) with flexible JSON metadata.

**RLS Policy** (Supabase):
```sql
-- Enable RLS
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own entities
CREATE POLICY "Users can view own entities"
ON entities FOR SELECT
USING (tenant_id = auth.uid() OR tenant_id = current_setting('request.jwt.claims', true)::json->>'user_id');
```

#### 4. `client_secrets` Table

```sql
CREATE TABLE client_secrets (
    user_id TEXT PRIMARY KEY,             -- FK to users.user_id
    wp_url TEXT NOT NULL,                 -- WordPress REST API endpoint
    wp_user TEXT NOT NULL,                -- WordPress username
    wp_password TEXT NOT NULL,            -- WordPress Application Password (encrypt in production)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
```

**Purpose**: Per-client WordPress credentials for multi-tenant publishing.

**Security Note**: Passwords should be encrypted at rest. For MVP, store as plain text but add encryption layer before production.

#### 5. `logs` Table

```sql
CREATE TABLE logs (
    id TEXT PRIMARY KEY,                  -- UUID
    tenant_id TEXT,                       -- FK to users.user_id (optional)
    action TEXT NOT NULL,                 -- e.g., 'agent_executed', 'lead_captured'
    details JSONB,                        -- Additional context
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_logs_tenant_id ON logs(tenant_id);
CREATE INDEX idx_logs_timestamp ON logs(timestamp);
```

**Purpose**: Audit trail for system actions.

---

### Entity JSON Structures (Exact Postgres Format)

#### **`anchor_location` Entity**

**Purpose**: Physical locations discovered via Google Maps scraping (courts, prisons, police stations).

**JSON Structure**:
```json
{
  "id": "loc_-8151703724190221143",
  "tenant_id": "admin@admin.com",
  "entity_type": "anchor_location",
  "name": "Auckland Central Remand Prison",
  "primary_contact": "09 638 1700",
  "metadata": {
    "name": "Auckland Central Remand Prison",
    "source_query": "Prisons in Auckland",
    "google_maps_url": "https://www.google.co.nz/maps/place/Auckland+Central+Remand+Prison",
    "address": "1 Lauder Road, Mount Eden, Auckland 1024",
    "phone": "09 638 1700",
    "website": "http://corrections.govt.nz/"
  },
  "created_at": "2026-01-16T01:05:20Z"
}
```

**Relationships**: 
- Referenced by `seo_keyword` entities via `metadata.target_id`

**Created By**: `ScoutAgent` (task: `scout_anchors`)

---

#### **`seo_keyword` Entity**

**Purpose**: SEO keywords generated from anchor locations for content targeting.

**JSON Structure**:
```json
{
  "id": "kw_-3245983666683810320",
  "tenant_id": "admin@admin.com",
  "entity_type": "seo_keyword",
  "name": "get out of jail help Auckland 1010",
  "primary_contact": null,
  "metadata": {
    "target_anchor": "Auckland District Court",
    "target_id": "loc_-1616333699436201666",
    "city": "Auckland 1010",
    "status": "published"  // "pending" → "published" (updated by SeoWriterAgent)
  },
  "created_at": "2026-01-16T01:10:15Z"
}
```

**Status Flow**:
- `"pending"`: Generated but not yet written
- `"published"`: Page created, keyword is live

**Relationships**:
- Links to `anchor_location` via `metadata.target_id`
- Referenced by `page_draft` via `metadata.keyword_id`

**Created By**: `SeoKeywordAgent` (task: `seo_keyword`)

---

#### **`page_draft` Entity**

**Purpose**: HTML landing page drafts in various stages of completion.

**JSON Structure**:
```json
{
  "id": "page_kw_-3245983666683810320",
  "tenant_id": "admin@admin.com",
  "entity_type": "page_draft",
  "name": "get out of jail help Auckland 1010",
  "primary_contact": null,
  "metadata": {
    "keyword_id": "kw_-3245983666683810320",
    "status": "published",  // "draft" → "published"/"live"
    "city": "Auckland 1010",
    "image_url": "https://images.unsplash.com/photo-1600119616692-d08f445b90b7?...",
    "has_tool": true,
    "content": "<div class=\"featured-image\">...<h1>Urgent Get Out of Jail Help in Auckland 1010</h1>...<script type=\"application/ld+json\">...</script>"
  },
  "created_at": "2026-01-16T01:15:30Z"
}
```

**Metadata Fields**:
- `keyword_id`: Links to source `seo_keyword`
- `status`: `"draft"` → `"published"` → `"live"`
- `city`: Geographic targeting
- `image_url`: Featured image from Unsplash (added by MediaAgent)
- `has_tool`: Boolean flag (set by UtilityAgent when JS widget added)
- `content`: Full HTML body (includes image, text, tool, schema.org)

**Status Flow**:
1. `"draft"`: Created by SeoWriterAgent (no image, no tool)
2. `"draft"` + `image_url`: Enhanced by MediaAgent
3. `"draft"` + `image_url` + `has_tool: true`: Enhanced by UtilityAgent
4. `"published"`: Published to WordPress by PublisherAgent

**Created By**: `SeoWriterAgent` (task: `write_pages`)

---

#### **`lead` Entity**

**Purpose**: Captured leads from interactive forms on published pages.

**JSON Structure**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "admin@admin.com",
  "entity_type": "lead",
  "name": "Bail Cost Estimator - Auckland 1010",
  "primary_contact": "+64212345678",
  "metadata": {
    "source": "Bail Cost Estimator - Auckland 1010",
    "data": {
      "fullName": "John Doe",
      "phoneNumber": "+64212345678",
      "email": "john@example.com",
      "chargesOffence": "DUI",
      "urgency": "Urgent (Within 24 hours)",
      "estimatedBail": "$5,000"
    },
    "captured_at": "2026-01-16T14:30:00Z",
    "notified": false  // Set to true after Twilio SMS sent
  },
  "created_at": "2026-01-16T14:30:00Z"
}
```

**Metadata Fields**:
- `source`: Tool/page identifier (e.g., "Bail Cost Estimator - Auckland 1010")
- `data`: Form submission data (flexible structure based on tool type)
- `captured_at`: Timestamp when form was submitted
- `notified`: Boolean flag for SMS notification status

**Created By**: Client-side JavaScript form submission → `POST /api/leads`

**Future Processing**: 
- ManagerAgent can detect new leads and trigger Twilio SMS
- Lead dispatch logic: `lead.tenant_id` → `projects.user_id` → `dna.generated.yaml` → extract phone number

---

## The Engine: ManagerAgent Logic

### How ManagerAgent Decides What to Do Next

The ManagerAgent is the **orchestrator** that monitors the entire pipeline and determines the next action. It follows a **state machine pattern** with 5 phases.

#### Decision Flow

```
ManagerAgent._execute()
    │
    ├─→ 1. FETCH STATE
    │   └─→ Query database for:
    │       - anchor_location entities (count)
    │       - seo_keyword entities (count)
    │       - page_draft entities (count + metadata analysis)
    │
    ├─→ 2. ANALYZE PAGE STATES
    │   └─→ Calculate:
    │       - pages_with_images = count(metadata.image_url exists)
    │       - pages_with_tools = count(metadata.has_tool == true)
    │       - pages_published = count(metadata.status in ['published', 'live'])
    │
    ├─→ 3. LOAD DNA PROFILE
    │   └─→ memory.get_user_project(user_id) → project_id
    │       └─→ Load YAML from Supabase Storage: profiles/{project_id}/dna.generated.yaml
    │
    └─→ 4. EXECUTE DECISION TREE (execute_pseo_strategy)
        │
        ├─→ Phase 1: IF stats["Locations"] == 0
        │   └─→ Return: {status: "action_required", next_task: "scout_anchors", next_params: {queries: [...]}}
        │
        ├─→ Phase 2: IF stats["Keywords"] < (stats["Locations"] * 2)
        │   └─→ Return: {status: "action_required", next_task: "seo_keyword", next_params: {}}
        │
        ├─→ Phase 3: IF stats["Drafts"] < 1
        │   └─→ Return: {status: "action_required", next_task: "write_pages", next_params: {}}
        │
        ├─→ Phase 4a: IF stats["Drafts"] > stats["Enhanced (Img)"]
        │   └─→ Return: {status: "action_required", next_task: "enhance_media", next_params: {}}
        │
        ├─→ Phase 4b: IF stats["Enhanced (Img)"] > stats["Interactive (JS)"]
        │   └─→ Return: {status: "action_required", next_task: "enhance_utility", next_params: {}}
        │
        ├─→ Phase 5: IF stats["Interactive (JS)"] > stats["Live"]
        │   └─→ Return: {status: "action_required", next_task: "publish", next_params: {}}
        │
        └─→ Complete: IF all phases done
            └─→ Return: {status: "complete", message: "All Systems Live"}
```

### Decision Logic Details

#### Phase 1: Location Scouting
```python
if stats["Locations"] == 0:
    # Generate search queries from DNA profile
    queries = []
    for city in dna['scout_rules']['geo_scope']['cities']:
        for anchor in dna['scout_rules']['anchor_entities']:
            queries.append(f"{anchor} in {city}")
    
    return AgentOutput(
        status="action_required",
        next_task="scout_anchors",
        next_params={"queries": queries}
    )
```

**Trigger**: No anchor locations in database.

**Action**: ScoutAgent scrapes Google Maps for locations matching DNA profile criteria.

---

#### Phase 2: Keyword Generation
```python
if stats["Keywords"] < (stats["Locations"] * 2):
    # Target: 2 keywords per location
    return AgentOutput(
        status="action_required",
        next_task="seo_keyword",
        next_params={}
    )
```

**Trigger**: Fewer than 2 keywords per location.

**Action**: SeoKeywordAgent generates keyword templates and applies to each location.

---

#### Phase 3: Content Writing
```python
if stats["Drafts"] < 1:
    # Start writing if no drafts exist
    return AgentOutput(
        status="action_required",
        next_task="write_pages",
        next_params={}
    )
```

**Trigger**: No page drafts created yet.

**Action**: SeoWriterAgent writes HTML pages from pending keywords.

---

#### Phase 4a: Media Enhancement
```python
if stats["Drafts"] > stats["Enhanced (Img)"]:
    # Some drafts lack images
    return AgentOutput(
        status="action_required",
        next_task="enhance_media",
        next_params={}
    )
```

**Trigger**: More drafts exist than pages with images.

**Action**: MediaAgent searches Unsplash and adds featured images.

---

#### Phase 4b: Tool Enhancement
```python
if stats["Enhanced (Img)"] > stats["Interactive (JS)"]:
    # Some pages with images lack tools
    return AgentOutput(
        status="action_required",
        next_task="enhance_utility",
        next_params={}
    )
```

**Trigger**: More pages with images than pages with tools.

**Action**: UtilityAgent generates JavaScript widgets (lead magnets).

---

#### Phase 5: Publishing
```python
if stats["Interactive (JS)"] > stats["Live"]:
    # Some ready pages not yet published
    return AgentOutput(
        status="action_required",
        next_task="publish",
        next_params={}
    )
```

**Trigger**: More pages with tools than published pages.

**Action**: PublisherAgent posts to WordPress using client credentials.

---

### Future: Lead Processing Logic

**Planned Enhancement** (Not Yet Implemented):

```python
# In ManagerAgent._execute(), after checking pipeline phases:

# Check for new leads
leads = memory.get_entities(tenant_id=user_id, entity_type="lead")
new_leads = [l for l in leads if not l['metadata'].get('notified', False)]

if new_leads:
    # Load client DNA to get phone number
    project = memory.get_user_project(user_id)
    dna = load_dna(project['dna_path'])
    client_phone = dna['identity']['contact']['phone']
    
    # Send SMS via Twilio
    for lead in new_leads:
        send_sms(
            to=client_phone,
            body=f"New Lead: {lead['metadata']['data']['fullName']} - {lead['metadata']['data']['phoneNumber']}"
        )
        
        # Mark as notified
        memory.update_entity(lead['id'], {'notified': True})
    
    return AgentOutput(
        status="action_required",
        message="New leads detected. SMS notifications sent.",
        next_task="process_leads"
    )
```

---

## Deployment Guide

### Prerequisites

- Supabase account (free tier sufficient)
- Railway account (for API hosting)
- Vercel account (for Next.js frontend)
- Twilio account (for SMS notifications)
- Unsplash API key (free)
- Google Gemini API key
- WordPress site with REST API enabled

---

### Step 1: Supabase Database Setup

#### 1.1 Create Supabase Project

1. Go to [supabase.com](https://supabase.com)
2. Create new project
3. Note your **Project URL** and **anon key** (Settings → API)

#### 1.2 Run SQL Schema

Execute this SQL in Supabase SQL Editor:

```sql
-- ============================================
-- APEX OS - SUPABASE SCHEMA
-- ============================================

-- 1. USERS TABLE
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2. PROJECTS TABLE
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    niche TEXT,
    dna_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);

-- 3. ENTITIES TABLE (Master Data)
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    primary_contact TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY(tenant_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entities_tenant_id ON entities(tenant_id);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_tenant_type ON entities(tenant_id, entity_type);

-- 4. CLIENT_SECRETS TABLE
CREATE TABLE IF NOT EXISTS client_secrets (
    user_id TEXT PRIMARY KEY,
    wp_url TEXT NOT NULL,
    wp_user TEXT NOT NULL,
    wp_password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 5. LOGS TABLE
CREATE TABLE IF NOT EXISTS logs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT,
    action TEXT NOT NULL,
    details JSONB,
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_logs_tenant_id ON logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);

-- ============================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_secrets ENABLE ROW LEVEL SECURITY;
ALTER TABLE logs ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view own projects
CREATE POLICY "Users can view own projects"
ON projects FOR SELECT
USING (user_id = current_setting('request.jwt.claims', true)::json->>'user_id');

-- Policy: Users can view own entities
CREATE POLICY "Users can view own entities"
ON entities FOR SELECT
USING (tenant_id = current_setting('request.jwt.claims', true)::json->>'user_id');

-- Policy: Users can insert own entities
CREATE POLICY "Users can insert own entities"
ON entities FOR INSERT
WITH CHECK (tenant_id = current_setting('request.jwt.claims', true)::json->>'user_id');

-- Policy: Users can update own entities
CREATE POLICY "Users can update own entities"
ON entities FOR UPDATE
USING (tenant_id = current_setting('request.jwt.claims', true)::json->>'user_id');

-- Policy: Users can view own secrets
CREATE POLICY "Users can view own secrets"
ON client_secrets FOR SELECT
USING (user_id = current_setting('request.jwt.claims', true)::json->>'user_id');
```

**Note**: RLS policies use JWT claims. For Railway API, you'll need to set `request.jwt.claims` via a custom header or use service role key for backend operations.

#### 1.3 Create Storage Bucket

1. Go to **Storage** in Supabase dashboard
2. Create bucket: `profiles`
3. Set to **Private** (only service role can access)
4. Upload your DNA YAML files to `profiles/{project_id}/dna.generated.yaml`

---

### Step 2: Railway API Deployment

#### 2.1 Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Create new project
3. Connect your GitHub repository
4. Select the repository root

#### 2.2 Configure Environment Variables

In Railway dashboard, add these environment variables:

```bash
# Database (Supabase)
DATABASE_URL=postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres
# Or use Supabase connection string from Settings → Database

# Supabase
SUPABASE_URL=https://[PROJECT_ID].supabase.co
SUPABASE_SERVICE_ROLE_KEY=[SERVICE_ROLE_KEY]  # From Supabase Settings → API
SUPABASE_ANON_KEY=[ANON_KEY]

# Storage (Supabase)
SUPABASE_STORAGE_BUCKET=profiles

# AI Services
GOOGLE_API_KEY=[YOUR_GEMINI_API_KEY]
UNSPLASH_ACCESS_KEY=[YOUR_UNSPLASH_KEY]

# Twilio (Future)
TWILIO_ACCOUNT_SID=[YOUR_TWILIO_SID]
TWILIO_AUTH_TOKEN=[YOUR_TWILIO_TOKEN]
TWILIO_PHONE_NUMBER=[YOUR_TWILIO_NUMBER]

# CORS (Frontend)
CORS_ORIGINS=https://your-vercel-app.vercel.app,http://localhost:3000

# Logging
LOG_LEVEL=INFO
```

#### 2.3 Update Memory Manager for Postgres

**File**: `backend/core/memory.py`

Replace SQLite connection with Supabase Postgres:

```python
import psycopg2
from psycopg2.extras import RealDictCursor
import os

class MemoryManager:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        # ... rest of initialization
```

**Note**: You'll need to update all `sqlite3` calls to `psycopg2` and adjust SQL syntax (Postgres uses `$1, $2` instead of `?`).

#### 2.4 Deploy

Railway will auto-detect Python and install dependencies from `requirements.txt`. Ensure `requirements.txt` includes:

```
psycopg2-binary>=2.9.0
```

Railway will:
1. Install dependencies
2. Run `python backend/main.py`
3. Expose API on public URL (e.g., `https://your-api.railway.app`)

---

### Step 3: Vercel Frontend Deployment

#### 3.1 Create Vercel Project

1. Go to [vercel.com](https://vercel.com)
2. Import your GitHub repository
3. Select `frontend/` as root directory

#### 3.2 Configure Environment Variables

In Vercel dashboard, add:

```bash
NEXT_PUBLIC_API_URL=https://your-api.railway.app
```

#### 3.3 Deploy

Vercel will:
1. Detect Next.js
2. Install dependencies (`npm install`)
3. Build (`npm run build`)
4. Deploy to `https://your-app.vercel.app`

---

### Step 4: Update CORS in Railway

After Vercel deployment, update Railway `CORS_ORIGINS`:

```bash
CORS_ORIGINS=https://your-app.vercel.app,http://localhost:3000
```

Restart Railway service to apply changes.

---

## Lead Capture Integration

### Injecting Lead Capture Script into Client Website

The lead capture forms are embedded in published WordPress pages. However, you can also inject a standalone script into any external website.

#### Option 1: WordPress Plugin (Recommended)

Create a simple WordPress plugin that injects the lead capture form:

```php
<?php
/**
 * Plugin Name: Apex Lead Capture
 * Description: Embeds Apex OS lead capture form
 */

function apex_lead_capture_form() {
    $user_id = get_option('apex_user_id'); // Set in WordPress admin
    $api_url = get_option('apex_api_url'); // https://your-api.railway.app
    
    ?>
    <div id="apex-lead-form">
        <form id="apex-contact-form">
            <input type="text" name="fullName" placeholder="Full Name" required>
            <input type="tel" name="phoneNumber" placeholder="Phone" required>
            <input type="email" name="email" placeholder="Email" required>
            <textarea name="message" placeholder="Message"></textarea>
            <button type="submit">Send Inquiry</button>
        </form>
    </div>
    
    <script>
        document.getElementById('apex-contact-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData);
            
            try {
                const response = await fetch('<?php echo $api_url; ?>/api/leads', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: '<?php echo $user_id; ?>',
                        source: 'WordPress Contact Form',
                        data: data
                    })
                });
                
                const result = await response.json();
                if (result.success) {
                    alert('Thank you! We will contact you soon.');
                    e.target.reset();
                } else {
                    alert('Error: ' + result.message);
                }
            } catch (error) {
                console.error('Lead capture error:', error);
                alert('Error submitting form. Please try again.');
            }
        });
    </script>
    <?php
}
add_shortcode('apex_lead_form', 'apex_lead_capture_form');
```

**Usage**: Add `[apex_lead_form]` shortcode to any WordPress page.

#### Option 2: External Script Injection

For non-WordPress sites, inject this script:

```html
<!-- Add to <head> or before </body> -->
<script>
(function() {
    // Configuration
    const APEX_CONFIG = {
        apiUrl: 'https://your-api.railway.app',
        userId: 'client@example.com',
        source: 'External Website Contact Form'
    };
    
    // Create form HTML
    const formHTML = `
        <div id="apex-lead-capture" style="max-width: 500px; margin: 20px auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
            <h3>Get In Touch</h3>
            <form id="apex-form">
                <input type="text" name="fullName" placeholder="Name" required style="width: 100%; padding: 10px; margin: 5px 0;">
                <input type="tel" name="phoneNumber" placeholder="Phone" required style="width: 100%; padding: 10px; margin: 5px 0;">
                <input type="email" name="email" placeholder="Email" required style="width: 100%; padding: 10px; margin: 5px 0;">
                <textarea name="message" placeholder="Message" style="width: 100%; padding: 10px; margin: 5px 0; height: 100px;"></textarea>
                <button type="submit" style="width: 100%; padding: 12px; background: #007cba; color: white; border: none; border-radius: 4px; cursor: pointer;">
                    Submit
                </button>
            </form>
            <div id="apex-message" style="margin-top: 10px;"></div>
        </div>
    `;
    
    // Inject form
    document.addEventListener('DOMContentLoaded', function() {
        const container = document.getElementById('apex-lead-container') || document.body;
        container.insertAdjacentHTML('beforeend', formHTML);
        
        // Attach submit handler
        document.getElementById('apex-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData);
            
            const messageDiv = document.getElementById('apex-message');
            messageDiv.textContent = 'Submitting...';
            messageDiv.style.color = '#666';
            
            try {
                const response = await fetch(`${APEX_CONFIG.apiUrl}/api/leads`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: APEX_CONFIG.userId,
                        source: APEX_CONFIG.source,
                        data: data
                    })
                });
                
                const result = await response.json();
                if (result.success) {
                    messageDiv.textContent = '✓ Thank you! We will contact you soon.';
                    messageDiv.style.color = 'green';
                    e.target.reset();
                } else {
                    messageDiv.textContent = '✗ Error: ' + result.message;
                    messageDiv.style.color = 'red';
                }
            } catch (error) {
                messageDiv.textContent = '✗ Network error. Please try again.';
                messageDiv.style.color = 'red';
                console.error('Lead capture error:', error);
            }
        });
    });
})();
</script>

<!-- Add this where you want the form to appear -->
<div id="apex-lead-container"></div>
```

---

## Debugging Handbook

### Common Errors & Fixes

#### 1. CORS Errors

**Symptom**: Browser console shows:
```
Access to fetch at 'https://api.railway.app/api/leads' from origin 'https://app.vercel.app' has been blocked by CORS policy
```

**Cause**: Railway API not allowing Vercel origin.

**Fix**:
1. Check Railway environment variable `CORS_ORIGINS`
2. Ensure it includes your Vercel URL: `https://your-app.vercel.app`
3. Restart Railway service
4. Verify in `backend/main.py`:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=os.getenv("CORS_ORIGINS", "").split(","),
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

---

#### 2. Database Connection Timeout

**Symptom**: API returns `500 Internal Server Error` with message about database connection.

**Cause**: 
- Supabase connection string incorrect
- Network firewall blocking Railway → Supabase
- Supabase project paused (free tier)

**Fix**:
1. Verify `DATABASE_URL` in Railway:
   ```
   postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
   ```
2. Check Supabase project is active (not paused)
3. Verify Railway IP is not blocked (Supabase → Settings → Database → Connection Pooling)
4. Test connection locally:
   ```python
   import psycopg2
   conn = psycopg2.connect(os.getenv("DATABASE_URL"))
   print("Connected!")
   ```

---

#### 3. "Profile not found" Error

**Symptom**: Agent returns `AgentOutput(status="error", message="Profile 'bail_v1' not found.")`

**Cause**: 
- YAML file not uploaded to Supabase Storage
- `dna_path` in `projects` table incorrect
- Storage bucket permissions incorrect

**Fix**:
1. Check `projects` table:
   ```sql
   SELECT * FROM projects WHERE user_id = 'admin@admin.com';
   ```
   Verify `dna_path` is: `profiles/bail_v1/dna.generated.yaml`
2. Check Supabase Storage:
   - Go to Storage → `profiles` bucket
   - Verify file exists at correct path
3. Update `backend/core/config.py` to load from Supabase Storage instead of local filesystem

---

#### 4. "No WordPress credentials found" Error

**Symptom**: PublisherAgent returns error when trying to publish.

**Cause**: `client_secrets` table missing entry for user.

**Fix**:
1. Insert credentials:
   ```sql
   INSERT INTO client_secrets (user_id, wp_url, wp_user, wp_password)
   VALUES (
       'admin@admin.com',
       'https://site.com/wp-json/wp/v2/posts',
       'username',
       'app_password_here'
   );
   ```
2. Or use helper script: `python scripts/add_client.py`

---

#### 5. Agent Execution Fails Silently

**Symptom**: Agent returns `status="error"` but no details in logs.

**Cause**: Exception caught but not logged properly.

**Fix**:
1. Check Railway logs (Railway dashboard → Deployments → View Logs)
2. Verify logging is initialized:
   ```python
   # In backend/main.py
   from backend.core.logger import setup_logging
   setup_logging()  # Must be called BEFORE app creation
   ```
3. Check `logs/apex.log` file (if file logging enabled)
4. Verify agent implements `_execute()` not `run()`:
   ```python
   # Correct
   async def _execute(self, input_data: AgentInput) -> AgentOutput:
       # Your logic here
   
   # Wrong
   async def run(self, input_data: AgentInput) -> AgentOutput:
       # This will cause issues
   ```

---

#### 6. ManagerAgent Always Returns Same Phase

**Symptom**: ManagerAgent keeps suggesting same action (e.g., "Phase 1: Location Scouting") even after running it.

**Cause**: 
- Entities not being saved to database
- RLS filtering out entities (wrong `tenant_id`)
- Query not finding entities

**Fix**:
1. Check database directly:
   ```sql
   SELECT COUNT(*) FROM entities WHERE tenant_id = 'admin@admin.com' AND entity_type = 'anchor_location';
   ```
2. Verify `tenant_id` matches `user_id` in agent calls
3. Check ScoutAgent is actually saving:
   ```python
   # In ScoutAgent._execute()
   if memory.save_entity(entity_obj):
       self.logger.info(f"Saved entity: {entity_obj.id}")
   else:
       self.logger.error("Failed to save entity!")
   ```

---

#### 7. Lead Capture Not Working

**Symptom**: Form submits but no lead appears in database.

**Cause**:
- API endpoint not reachable
- CORS blocking request
- `user_id` mismatch
- Database insert failing

**Fix**:
1. Check browser Network tab:
   - Request URL: `https://api.railway.app/api/leads`
   - Status: Should be `200` or `201`
   - Response: Should have `{"success": true}`
2. Check Railway logs for `/api/leads` endpoint
3. Verify `user_id` in form matches database:
   ```sql
   SELECT * FROM users WHERE user_id = 'client@example.com';
   ```
4. Test endpoint directly:
   ```bash
   curl -X POST https://api.railway.app/api/leads \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "admin@admin.com",
       "source": "Test Form",
       "data": {"fullName": "Test User", "phone": "1234567890"}
     }'
   ```

---

#### 8. Supabase Storage File Not Found

**Symptom**: ConfigLoader fails to load YAML from Supabase Storage.

**Cause**: 
- File path incorrect
- Storage bucket permissions
- Supabase client not configured

**Fix**:
1. Update `backend/core/config.py`:
   ```python
   from supabase import create_client
   
   class ConfigLoader:
       def __init__(self):
           self.supabase = create_client(
               os.getenv("SUPABASE_URL"),
               os.getenv("SUPABASE_SERVICE_ROLE_KEY")
           )
       
       def load(self, niche: str) -> Dict[str, Any]:
           # Download from Storage
           path = f"profiles/{niche}/dna.generated.yaml"
           response = self.supabase.storage.from_("profiles").download(path)
           yaml_content = response.decode('utf-8')
           return yaml.safe_load(yaml_content)
   ```

---

### Debugging Tools

#### 1. Database Inspection

**Supabase SQL Editor**:
```sql
-- Check all entities for a user
SELECT entity_type, COUNT(*) 
FROM entities 
WHERE tenant_id = 'admin@admin.com' 
GROUP BY entity_type;

-- Check page status distribution
SELECT 
    metadata->>'status' as status,
    COUNT(*) 
FROM entities 
WHERE entity_type = 'page_draft' 
  AND tenant_id = 'admin@admin.com'
GROUP BY status;

-- Check recent leads
SELECT name, metadata->>'data'->>'fullName', created_at
FROM entities
WHERE entity_type = 'lead'
  AND tenant_id = 'admin@admin.com'
ORDER BY created_at DESC
LIMIT 10;
```

#### 2. API Testing

**Health Check**:
```bash
curl https://api.railway.app/
```

**Test Agent Execution**:
```bash
curl -X POST https://api.railway.app/api/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "manager",
    "user_id": "admin@admin.com",
    "params": {}
  }'
```

#### 3. Log Analysis

**Railway Logs**:
- Railway Dashboard → Your Service → Deployments → View Logs
- Filter by: `Apex.Manager`, `Apex.Scout`, etc.

**Local Logs** (if running locally):
```bash
tail -f logs/apex.log | grep "Apex.Manager"
```

---

## API Reference

### Endpoints

#### `GET /`
Health check endpoint.

**Response**:
```json
{
  "status": "online",
  "system": "Apex Kernel",
  "version": "1.0",
  "loaded_agents": ["onboarding", "scout", "manager", ...]
}
```

---

#### `POST /api/run`
Execute an agent task.

**Request**:
```json
{
  "task": "manager",
  "user_id": "admin@admin.com",
  "params": {}
}
```

**Response**:
```json
{
  "status": "action_required",
  "message": "Phase 1: Location Scouting",
  "data": {
    "step": "1_scout",
    "description": "I need to find target locations...",
    "stats": {
      "Locations": 0,
      "Keywords": 0,
      "Drafts": 0
    },
    "action_label": "Launch Scout",
    "next_task": "scout_anchors",
    "next_params": {
      "queries": ["Courts in Auckland", "Prisons in Auckland"]
    }
  },
  "timestamp": "2026-01-16T10:30:00Z"
}
```

**Status Values**:
- `"action_required"`: Next step available (check `data.next_task`)
- `"complete"`: All phases done, system monitoring
- `"success"`: Task completed successfully
- `"error"`: Task failed (check `message`)

---

#### `POST /api/leads`
Capture a lead from external form.

**Request**:
```json
{
  "user_id": "admin@admin.com",
  "source": "Bail Cost Estimator - Auckland 1010",
  "data": {
    "fullName": "John Doe",
    "phoneNumber": "+64212345678",
    "email": "john@example.com",
    "chargesOffence": "DUI",
    "urgency": "Urgent (Within 24 hours)"
  }
}
```

**Response**:
```json
{
  "success": true,
  "lead_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Lead captured successfully"
}
```

---

#### `GET /api/entities`
Retrieve entities for a user (RLS enforced).

**Query Parameters**:
- `user_id` (required): User identifier
- `entity_type` (optional): Filter by type (`anchor_location`, `seo_keyword`, `page_draft`, `lead`)

**Response**:
```json
{
  "entities": [
    {
      "id": "loc_123",
      "tenant_id": "admin@admin.com",
      "entity_type": "anchor_location",
      "name": "Auckland District Court",
      "primary_contact": "09 123 4567",
      "metadata": {...},
      "created_at": "2026-01-16T01:05:20Z"
    }
  ]
}
```

---

#### `POST /api/auth/verify`
Verify user credentials.

**Request**:
```json
{
  "email": "admin@admin.com",
  "password": "password123"
}
```

**Response**:
```json
{
  "success": true,
  "user_id": "admin@admin.com"
}
```

---

## Migration Checklist: SQLite → Supabase

### Code Changes Required

1. **Update `backend/core/memory.py`**:
   - Replace `sqlite3` with `psycopg2`
   - Change SQL syntax: `?` → `$1, $2, $3`
   - Update connection string to use `DATABASE_URL`

2. **Update `backend/core/config.py`**:
   - Replace file system reads with Supabase Storage API
   - Use `supabase.storage.from_("profiles").download(path)`

3. **Update `backend/main.py`**:
   - Add Supabase client initialization
   - Update CORS origins to include Vercel URL

4. **Environment Variables**:
   - Add `DATABASE_URL` (Supabase connection string)
   - Add `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
   - Update `CORS_ORIGINS` with production URLs

5. **Dependencies**:
   - Add `psycopg2-binary>=2.9.0` to `requirements.txt`
   - Add `supabase>=2.0.0` to `requirements.txt`

---

## Production Considerations

### Security

1. **Encrypt `client_secrets.wp_password`**:
   - Use `cryptography` library
   - Encrypt before storing, decrypt when retrieving

2. **Use Service Role Key Carefully**:
   - Only in backend (Railway)
   - Never expose to frontend
   - Use Anon Key for public operations

3. **Rate Limiting**:
   - Add rate limiting to `/api/leads` endpoint
   - Prevent spam/abuse

4. **Input Validation**:
   - Validate all user inputs
   - Sanitize HTML content before publishing

### Performance

1. **Database Indexing**:
   - All foreign keys indexed
   - Composite index on `(tenant_id, entity_type)` for common queries

2. **Connection Pooling**:
   - Use Supabase Connection Pooler
   - Set `DATABASE_URL` to pooler endpoint

3. **Caching**:
   - Cache DNA profiles (YAML files) in memory
   - Refresh on file update

### Monitoring

1. **Error Tracking**:
   - Integrate Sentry or similar
   - Track agent failures

2. **Metrics**:
   - Track agent execution times
   - Monitor lead capture rate
   - Dashboard for system health

---

**Last Updated**: 2026-01-16  
**Maintainer**: Apex OS Development Team  
**Questions?**: Check `architecture.md` for system overview
