# Frontend Architecture

## Overview
Next.js 14 application with App Router, React 18, TypeScript, and Tailwind CSS. Built with a "Mission Control" design philosophy - minimal, visual, and action-oriented.

## Tech Stack

- **Framework**: Next.js 14.2.0 (App Router)
- **Runtime**: React 18.3.0
- **Language**: TypeScript 5.4.0
- **Styling**: Tailwind CSS 3.4.0
- **Data Fetching**: SWR 2.2.5
- **HTTP Client**: Axios 1.7.0
- **Icons**: Lucide React 0.400.0
- **UI Components**: Custom components built with Tailwind + shadcn/ui patterns

## Project Structure

```
frontend/
├── app/                      # Next.js App Router pages
│   ├── dashboard/
│   │   ├── page.tsx         # Mission Control (main dashboard)
│   │   ├── assets/          # Content Library (drafts, locations, keywords)
│   │   ├── console/         # Agent Console
│   │   ├── leads/           # Leads management
│   │   ├── settings/        # Settings page
│   │   └── layout.tsx       # Dashboard layout with sidebar
│   ├── layout.tsx           # Root layout
│   └── page.tsx             # Landing/auth page
│
├── components/
│   ├── dashboard/
│   │   ├── PipelineTracker.tsx   # 9-stage pipeline visualization
│   │   ├── GlobalStatus.tsx      # Large status indicator
│   │   ├── ArticleCard.tsx       # Draft/article card component
│   │   ├── ReviewQueue.tsx       # Review queue component
│   │   ├── StatsGrid.tsx         # Stats grid
│   │   ├── AgentConsole.tsx      # Agent execution console
│   │   └── AssetTable.tsx        # Entity table component
│   ├── layout/
│   │   ├── Header.tsx            # Top header bar
│   │   └── Sidebar.tsx           # Navigation sidebar
│   ├── onboarding/
│   │   └── OnboardingWizard.tsx  # New project wizard
│   └── ui/                       # Reusable UI components
│       ├── button.tsx
│       ├── card.tsx
│       ├── badge.tsx
│       ├── table.tsx
│       ├── input.tsx
│       └── label.tsx
│
├── hooks/                   # Custom React hooks
│   ├── useAuth.tsx          # Authentication hook
│   ├── useEntities.ts       # Entity data fetching
│   ├── useLeads.ts          # Leads data fetching
│   ├── useManagerStatus.ts  # Manager status polling
│   ├── useProjects.ts       # Projects management
│   └── useProjectContext.tsx # Project context provider
│
├── lib/                     # Utilities and core logic
│   ├── api.ts               # API client (Axios)
│   ├── auth.ts              # Auth utilities
│   ├── types.ts             # TypeScript interfaces
│   └── utils.ts             # Utility functions (cn, etc.)
│
└── globals.css              # Global styles + Tailwind

```

## Key Architectural Patterns

### 1. **Data Fetching with SWR**
- All data fetching uses SWR for automatic caching, revalidation, and polling
- 10-second polling interval for real-time updates
- Optimistic updates for user actions

### 2. **Component Hierarchy**

```
App Layout
└── Dashboard Layout (Sidebar + Header)
    ├── Mission Control (Dashboard)
    │   ├── GlobalStatus
    │   ├── PipelineTracker
    │   └── StatsGrid
    ├── Content Library (Assets)
    │   └── ArticleCard grid
    ├── Agent Console
    ├── Leads
    └── Settings
```

### 3. **State Management**
- **Server State**: SWR for API data (cached, auto-refreshing)
- **Client State**: React Context (`useProjectContext`) for active project
- **Form State**: React `useState` for settings and forms

### 4. **API Integration**
- Single Axios client in `lib/api.ts`
- All endpoints go through `/api/run` with task-based routing
- Backend handles agent orchestration

## Design System

### Color Palette
- **Primary**: Purple (`#a855f7`) - main brand color
- **Secondary**: Amber/Gold (`#fbbf24`) - accents and warnings
- **Success**: Emerald (green) - completed states
- **Active**: Blue - processing states
- **Error**: Red - errors and rejections
- **Background**: Slate 950/900 - dark theme

### Status Indicators
- **Green**: Complete/success
- **Blue**: Active/processing
- **Amber**: Needs attention/warning
- **Gray**: Pending/not started

### Components Philosophy
- **Minimalist**: Hide raw data, show visual indicators
- **Visual**: Icons, badges, progress bars over text lists
- **Action-Oriented**: "What needs attention?" is immediately visible

## Pipeline Visualization

The `PipelineTracker` component visualizes the 9-stage content production pipeline:

1. **Scout** → Find anchor locations
2. **Strategy** → Generate keywords
3. **Writer** → Write page drafts
4. **Critic** → Review drafts (quality scores)
5. **Librarian** → Add internal links
6. **Media** → Fetch images
7. **Utility** → Add lead gen tools
8. **Publisher** → Publish pages
9. **Analytics** → Audit performance

Each stage shows:
- Icon (Lucide React)
- Stage name
- Count badge (number of items)
- Status color (complete/active/attention/pending)
- Connecting lines (pipeline flow)

## Data Flow

```
Backend Manager Agent
    ↓
/api/run (task="manager")
    ↓
useManagerStatus hook (SWR, 10s poll)
    ↓
Dashboard Components:
    ├── GlobalStatus (data.step, data.action_label)
    ├── PipelineTracker (data.stats pipeline counts)
    └── StatsGrid (data.stats summary)
```

## Routing

All routes are under `/dashboard`:
- `/dashboard` - Mission Control (main)
- `/dashboard/assets` - Content Library
- `/dashboard/console` - Agent Console
- `/dashboard/leads` - Leads management
- `/dashboard/settings` - Settings

## Authentication

- Session-based auth with user_id
- Protected routes via `useRequireAuth` hook
- Project-scoped data (all entities tied to project_id)

## Responsive Design

- **Mobile-first**: Base styles for mobile
- **Breakpoints**: `md:` (768px), `lg:` (1024px), `xl:` (1280px)
- **Grid layouts**: 1 column mobile → 2-4 columns desktop

## Future Considerations

- Preview modal for drafts
- Real-time WebSocket updates (replace polling)
- Draft approval/rejection API endpoints
- Settings save API integration
- Advanced filtering and search
