# Apex Sovereign OS - Next.js Dashboard

Professional Next.js 14 dashboard for the Apex Sovereign OS backend system.

## Tech Stack

- **Next.js 14** (App Router)
- **TypeScript**
- **Tailwind CSS** (Dark theme with purple/gold accents)
- **Shadcn/UI** (Button, Card, Badge, Table components)
- **SWR** (Data fetching with 10s polling)
- **Axios** (API client)

## Setup

1. **Install dependencies:**

   ```bash
   cd frontend
   npm install
   ```

2. **Set environment variables** (optional):
   Create a `.env.local` file:

   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

3. **Run development server:**

   ```bash
   npm run dev
   ```

4. **Open browser:**
   Navigate to `http://localhost:3000`

## Features

### Login Page (`/`)

- Mock authentication using localStorage
- Email/password form
- Redirects to dashboard on success

### Mission Control (`/dashboard`)

- Stats grid showing Locations Found, Pages Written, Leads Captured
- Real-time status from manager agent
- Current directive display with action buttons

### Asset Database (`/dashboard/assets`)

- Tabbed interface for viewing entities:
  - Locations (anchor_location)
  - Keywords (seo_keyword)
  - Pages (page_draft)
- Real-time data updates (10s polling)

### Agent Console (`/dashboard/console`)

- Terminal-like interface
- Buttons to run agents (Scout, Keywords, Writer, etc.)
- Real-time log streaming with polling (2.5s intervals)
- Progress indicators and status updates

## Backend Integration

The frontend connects to the FastAPI backend at `localhost:8000` by default.

**Endpoints used:**

- `POST /api/run` - Execute agents
- `GET /` - Health check

**Note:** The current backend doesn't expose direct entity endpoints. The Asset Database will need a backend endpoint like:

- `GET /api/entities?entity_type=anchor_location&user_id=xxx`

For MVP, the Asset Database uses placeholder data until the backend endpoint is added.

## Authentication

Uses mock JWT authentication:

- Token stored in localStorage
- No actual backend verification required for MVP
- Can be upgraded to real JWT later

## Design

- **Theme:** Dark mode (slate-950 background)
- **Primary Color:** Purple (#a855f7) with neon glow
- **Accent Color:** Gold/Amber (#fbbf24)
- **Style:** Cyberpunk/enterprise aesthetic, high-density data presentation

## Project Structure

```
frontend/
├── app/                          # Next.js App Router
│   ├── layout.tsx               # Root layout
│   ├── page.tsx                 # Login page
│   ├── globals.css              # Global styles
│   └── dashboard/               # Dashboard pages
│       ├── layout.tsx           # Dashboard layout (sidebar)
│       ├── page.tsx             # Mission Control
│       ├── assets/page.tsx      # Asset Database
│       └── console/page.tsx     # Agent Console
├── components/
│   ├── ui/                      # Shadcn UI components
│   ├── layout/                  # Layout components
│   └── dashboard/               # Dashboard components
├── lib/                         # Utilities and API client
├── hooks/                       # React hooks (SWR, auth)
└── public/                      # Static assets
```

## Development

- **Linting:** `npm run lint`
- **Build:** `npm run build`
- **Start production:** `npm start`

## Notes

- Entity fetching currently requires backend support for `GET /api/entities` endpoint
- Agent console polling can be upgraded to WebSocket for real-time updates
- Mock auth can be replaced with real JWT authentication
