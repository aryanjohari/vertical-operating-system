/**
 * Data layer types — contract with FastAPI backend.
 */

// Auth & Projects
export interface Project {
  project_id: string;
  user_id: string;
  niche: string;
  dna_path?: string;
  created_at?: string;
}

// Base entity (memory record)
export interface Entity {
  id: string;
  project_id: string | null;
  entity_type: string;
  tenant_id: string;
  name: string;
  primary_contact: string | null;
  status?: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface SeoKeyword extends Entity {
  entity_type: "seo_keyword";
  metadata: Entity["metadata"] & { keyword?: string; [key: string]: unknown };
}

export interface PageDraft extends Entity {
  entity_type: "page_draft";
  metadata: Entity["metadata"] & { slug?: string; status?: string; [key: string]: unknown };
}

export interface Lead extends Entity {
  entity_type: "lead";
  metadata: Entity["metadata"] & { source?: string; score?: number; [key: string]: unknown };
}

// Analytics API contracts
export interface LeadGenAnalytics {
  from: string;
  to: string;
  webhooks_received: number;
  avg_lead_score: number | null;
  scheduled_bridge: { count: number; total: number; pct: number };
  by_source?: Record<string, number>;
}

export interface PseoAnalytics {
  from: string;
  to: string;
  gsc_connected: boolean;
  organic_clicks: number;
  organic_impressions: number;
  ctr: number;
  filtered_pages_count: number;
  per_page?: { url: string; clicks: number; impressions: number; ctr: number }[];
}

export interface GscStatus {
  connected: boolean;
}

export interface AnalyticsSnapshotResponse<T = LeadGenAnalytics | PseoAnalytics> {
  fetched_at: string | null;
  payload: T | null;
}
