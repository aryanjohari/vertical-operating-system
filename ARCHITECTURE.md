# Apex Vertical Operating System - Architecture

## Overview

Apex is a vertical operating system for revenue automation, built on an agent-based architecture. It provides programmatic SEO, lead generation, and business automation through a modular system of specialized AI agents.

**Core Philosophy:** Agents are autonomous workers that operate on project-specific DNA configurations, enabling multi-tenant, project-scoped automation.

## System Architecture

### High-Level Flow

```
Frontend (Next.js) → FastAPI (/api/run) → Kernel → Agent → Memory/Storage
```

### Core Components

#### 1. **Kernel** (`backend/core/kernel.py`)
The central dispatcher and orchestrator:
- **Agent Registry**: Dynamically loads agents from `AgentRegistry.DIRECTORY`
- **Task Routing**: Maps task names to agents (exact match → prefix match)
- **Context Injection**: Loads DNA configs and injects into agents
- **Security**: Validates project ownership before execution
- **System Agents**: Bypass DNA loading (e.g., `onboarding`)

**Key Methods:**
- `dispatch(packet: AgentInput) → AgentOutput`: Main entry point
- `_resolve_agent(task: str) → str`: Smart agent resolution
- `_boot_agents()`: Dynamic agent registration at startup

#### 2. **BaseAgent** (`backend/core/agent_base.py`)
Abstract base class for all agents:
- **Injected Context**: `config`, `project_id`, `user_id` (set by Kernel)
- **Lifecycle**: `run()` → `_execute()` with error handling
- **Logging**: Automatic snapshot recording (optional)
- **Interface**: All agents implement `async _execute(input: AgentInput) → AgentOutput`

#### 3. **Memory** (`backend/core/memory.py`)
Dual-storage system:
- **SQLite** (`data/apex.db`): Structured data (users, projects, entities, secrets)
- **ChromaDB** (`data/chroma_db`): Vector embeddings for RAG (Google `text-embedding-004`)
- **RLS**: Row-level security via `tenant_id` (user isolation)

**Key Features:**
- Project ownership verification
- Entity CRUD with metadata JSON
- Context saving for RAG (insider tips, knowledge nuggets)
- Encrypted secrets storage

#### 4. **Config System** (`backend/core/config.py`)
DNA profile management:
- **Template**: `profile_template.yaml` (universal structure)
- **Loading**: Merges `dna.generated.yaml` + `dna.custom.yaml`
- **Location**: `data/profiles/{project_id}/`
- **Structure**: Identity → Brand Brain → Services → Modules → System

## Module Architecture

### Module Structure

Each module follows this pattern:
```
modules/{module_name}/
  ├── manager.py          # Orchestrator agent
  └── agents/
      ├── agent1.py       # Worker agents
      └── agent2.py
```

### Active Modules

#### 1. **Onboarding** (`modules/onboarding/`)
**Purpose**: Project initialization and DNA generation

**Agent**: `OnboardingAgent`
- **Action**: `compile_profile`
- **Flow**: Scrape (optional) → Compile → Save → RAG
- **Input**: Form data (identity + modules)
- **Output**: `dna.generated.yaml` + project registration

**Frontend**: 3-step wizard (Module Selection → Business DNA → Genesis)

#### 2. **pSEO** (`modules/pseo/`)
**Purpose**: Programmatic SEO for Google Maps dominance

**Manager**: `ManagerAgent` (task: `manager`)
- Orchestrates pipeline: Scout → Strategist → Writer → Critic → Librarian → Media → Publisher → Analytics

**Agents**:
- `scout_anchors`: Find anchor locations
- `strategist_run`: Generate keywords
- `write_pages`: Create content
- `critic_review`: Quality check
- `librarian_link`: Add internal links
- `enhance_media`: Add images
- `publish`: Deploy to WordPress
- `analytics_audit`: Performance feedback

**Frontend**: Dashboard with pipeline visualization

#### 3. **Lead Gen** (`modules/lead_gen/`)
**Purpose**: Active lead generation and speed-to-lead

**Manager**: `LeadGenManager` (task: `lead_gen_manager`)
- **Actions**: `hunt_sniper`, `ignite_reactivation`, `instant_call`, `dashboard_stats`

**Agents**:
- `sniper_agent`: Scrape leads from platforms
- `sales_agent`: Bridge calls (Twilio integration)
- `reactivator_agent`: SMS reactivation campaigns
- `lead_scorer`: Score leads by quality
- `enhance_utility`: Build lead magnets

**Frontend**: Dashboard with stats, actions, and leads table

## Backend Structure

```
backend/
├── core/                 # Core system components
│   ├── agent_base.py     # BaseAgent abstract class
│   ├── kernel.py         # Central dispatcher
│   ├── memory.py         # SQLite + ChromaDB
│   ├── config.py         # DNA profile loader
│   ├── registry.py       # Agent registry
│   ├── models.py         # Pydantic models
│   ├── auth.py           # JWT authentication
│   ├── security.py        # Encryption/decryption
│   ├── logger.py          # Logging setup
│   └── services/         # Shared services
│       ├── llm_gateway.py    # Gemini API wrapper
│       ├── universal.py      # Web scraper (Playwright)
│       └── maps_sync.py      # Google Maps sync
├── modules/              # Business modules
│   ├── onboarding/
│   ├── pseo/
│   └── lead_gen/
├── routers/              # FastAPI routers
│   ├── voice.py          # Voice/webhook endpoints
│   └── webhooks.py       # External webhooks
└── main.py               # FastAPI app + /api/run endpoint
```

## Frontend Structure

```
frontend/
├── app/                  # Next.js App Router
│   ├── (auth)/           # Auth routes
│   ├── (dashboard)/     # Protected routes
│   │   ├── onboarding/   # Wizard
│   │   ├── dashboard/    # Main dashboard
│   │   └── projects/[id]/ # Project pages
│   │       ├── page.tsx      # pSEO dashboard
│   │       ├── lead-gen/     # Lead Gen dashboard
│   │       ├── entities/     # Entity manager
│   │       ├── settings/      # DNA editor
│   │       └── integrations/ # WordPress/GSC
│   └── layout.tsx
├── components/           # React components
│   ├── project/          # Project-specific
│   ├── leadgen/          # Lead Gen UI
│   ├── entities/         # Entity management
│   ├── onboarding/       # Wizard components
│   └── ui/               # Reusable UI
└── lib/                  # Utilities
    ├── api.ts            # Axios client
    ├── auth.ts           # Auth helpers
    ├── store.ts          # Zustand stores
    └── types.ts           # TypeScript types
```

## Data Flow

### Request Flow

1. **Frontend** → `POST /api/run` with `AgentInput`
2. **main.py** → Validates JWT, extracts `user_id`
3. **Kernel** → Resolves agent, loads DNA, verifies ownership
4. **Agent** → Executes `_execute()`, returns `AgentOutput`
5. **Kernel** → Returns to `/api/run`
6. **main.py** → Returns JSON to frontend

### Agent Execution

```
AgentInput (task, user_id, params)
    ↓
Kernel.dispatch()
    ↓
Load DNA Config (if not system agent)
    ↓
Inject Context (config, project_id, user_id)
    ↓
Agent.run() → Agent._execute()
    ↓
AgentOutput (status, data, message)
```

### DNA Configuration

**Location**: `data/profiles/{project_id}/dna.generated.yaml`

**Structure**:
```yaml
identity:
  project_id: string
  business_name: string
  niche: string
  contact: {phone, email, address}

brand_brain:
  voice_tone: string
  key_differentiators: []
  insider_tips: []
  common_objections: []
  forbidden_topics: []

modules:
  local_seo:
    enabled: bool
    scout_settings: {...}
    publisher_settings: {...}
  lead_gen:
    enabled: bool
    sniper: {...}
    sales_bridge: {...}
```

## API Endpoints

### Core
- `POST /api/run` - Universal agent dispatcher
- `POST /api/auth/verify` - Login (returns JWT)
- `POST /api/auth/register` - User registration

### Entities
- `GET /api/entities` - List entities (with filters)
- `POST /api/entities` - Create entity
- `PUT /api/entities/{id}` - Update entity
- `DELETE /api/entities/{id}` - Delete entity

### Projects
- `GET /api/projects` - List user projects
- `POST /api/projects` - Create project (triggers onboarding)

### Configuration
- `GET /api/projects/{id}/dna` - Get DNA config
- `PUT /api/projects/{id}/dna` - Update DNA config

### Voice/Webhooks
- `POST /api/voice/call` - Inbound call handling
- `POST /api/webhooks/*` - External webhooks

## Storage

### SQLite (`data/apex.db`)
**Tables**:
- `users`: User accounts (hashed passwords)
- `projects`: Project registry
- `entities`: All data entities (leads, keywords, pages, etc.)
- `client_secrets`: Encrypted credentials

**Security**: Row-level via `tenant_id` (user isolation)

### ChromaDB (`data/chroma_db`)
**Collection**: `apex_context`
- **Purpose**: RAG for brand brain knowledge
- **Embeddings**: Google `text-embedding-004`
- **Metadata**: `{type, source, project_id}`

### YAML Profiles (`data/profiles/{project_id}/`)
- `dna.generated.yaml`: AI-generated (read-only)
- `dna.custom.yaml`: User overrides (merged)

## Security

### Authentication
- **JWT**: Bearer tokens in `Authorization` header
- **Validation**: `get_current_user` dependency in FastAPI
- **Storage**: Tokens in Zustand store (frontend)

### Authorization
- **Project Ownership**: Verified before DNA loading
- **RLS**: All queries filtered by `tenant_id`
- **Agent Isolation**: Agents only see their project's DNA

### Data Protection
- **Passwords**: Hashed with salt (bcrypt-like)
- **Secrets**: Encrypted via `security_core`
- **Input Validation**: Pydantic models + regex sanitization

## Agent Development

### Creating a New Agent

1. **Create Agent Class**:
```python
from backend.core.agent_base import BaseAgent, AgentInput, AgentOutput

class MyAgent(BaseAgent):
    async def _execute(self, input_data: AgentInput) -> AgentOutput:
        # Access: self.config, self.project_id, self.user_id
        return AgentOutput(status="success", data={...})
```

2. **Register in Registry**:
```python
# backend/core/registry.py
DIRECTORY = {
    "my_agent": ("backend.modules.my_module.agents.my_agent", "MyAgent"),
}
```

3. **Call from Frontend**:
```typescript
await api.post('/api/run', {
  task: 'my_agent',
  params: { project_id, ... }
});
```

## Technology Stack

### Backend
- **FastAPI**: Web framework
- **SQLite**: Relational database
- **ChromaDB**: Vector database
- **Playwright**: Web scraping
- **Google Gemini**: LLM (via `llm_gateway`)
- **Pydantic**: Data validation

### Frontend
- **Next.js 16**: React framework
- **TypeScript**: Type safety
- **Tailwind CSS**: Styling
- **Zustand**: State management
- **React Query**: Data fetching
- **React Hook Form**: Form handling

## Key Design Patterns

1. **Agent Pattern**: Autonomous workers with injected context
2. **Registry Pattern**: Centralized agent discovery
3. **DNA Pattern**: Project-specific configuration
4. **RLS Pattern**: Multi-tenant data isolation
5. **RAG Pattern**: Vector embeddings for knowledge retrieval

## Deployment Notes

- **Backend**: Python 3.9+, requires `GOOGLE_API_KEY`
- **Frontend**: Node.js 18+, Next.js production build
- **Storage**: Local filesystem (SQLite, ChromaDB, YAML)
- **Scraping**: Playwright requires Chromium binary

---

**Version**: 3.0 (Titanium Kernel)  
**Last Updated**: 2024
