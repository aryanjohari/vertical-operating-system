/**
 * Data Layer Types — The Contract with the FastAPI Backend
 * All entity types align with backend/core/models.py and memory schema.
 */

// ==========================================
// AUTH & PROJECTS
// ==========================================

export interface User {
  id: string; // user_id from backend (email)
}

export interface Project {
  project_id: string;
  user_id: string;
  niche: string;
  dna_path?: string;
  created_at?: string;
}

// ==========================================
// BASE ENTITY (Universal Memory Record)
// ==========================================

export interface Entity {
  id: string;
  project_id: string | null;
  entity_type: string;
  tenant_id: string;
  name: string;
  primary_contact: string | null;
  status?: string; // Often in metadata.status for leads
  created_at: string;
  metadata: Record<string, unknown>;
}

// ==========================================
// ENTITY VARIANTS (Extend Base)
// ==========================================

export interface SeoKeyword extends Entity {
  entity_type: "seo_keyword";
  metadata: Entity["metadata"] & {
    keyword?: string;
    search_volume?: number;
    difficulty?: number;
    intent?: string;
    [key: string]: unknown;
  };
}

export type PageDraftStatus =
  | "processing"
  | "drafted"
  | "draft"
  | "in_review"
  | "needs_revision"
  | "approved"
  | "published"
  | string;

export interface PageDraft extends Entity {
  entity_type: "page_draft";
  metadata: Entity["metadata"] & {
    title?: string;
    slug?: string;
    content?: string;
    status?: PageDraftStatus;
    [key: string]: unknown;
  };
}

export interface Lead extends Entity {
  entity_type: "lead";
  metadata: Entity["metadata"] & {
    source?: string;
    status?:
      | "new"
      | "contacted"
      | "calling"
      | "called"
      | "converted"
      | "spam_blocked";
    phone?: string;
    email?: string;
    score?: number;
    call_sid?: string;
    call_duration?: number;
    call_transcription?: string;
    data?: Record<string, unknown>;
    description?: string;
    [key: string]: unknown;
  };
}

// ==========================================
// CAMPAIGN CONFIG (YAML Structure)
// Merged structure from lead_gen_default, pseo_default, profile_template
// ==========================================

export interface FormFieldConfig {
  name: string;
  type: "text" | "tel" | "email" | "textarea" | "select" | "checkbox";
  label: string;
  required?: boolean;
  options?: { value: string; label: string }[];
}

export interface FormSettings {
  enabled: boolean;
  fields: FormFieldConfig[];
}

export interface BusinessHoursConfig {
  timezone?: string;
  start_hour?: number;
  end_hour?: number;
}

export interface SalesBridgeConfig {
  destination_phone: string;
  whisper_text?: string;
  sms_alert_template?: string;
  /** Email for manual bridge-review notifications (high-value leads). */
  bridge_review_email?: string;
  /** Only leads with score >= this get bridge-review email and can be bridged. Default 90. */
  min_score_to_ring?: number;
  /** Bridging allowed only within these hours (project timezone). */
  business_hours?: BusinessHoursConfig;
  /** Optional list of dates when bridging is disabled, e.g. ["2025-12-25"]. */
  holidays?: string[];
}

export interface NurturingConfig {
  enabled?: boolean;
  missed_call_sms?: string;
}

export interface LeadGenModuleConfig {
  form_settings?: FormSettings;
  sales_bridge?: SalesBridgeConfig;
  nurturing?: NurturingConfig;
  scoring_rules?: Record<string, unknown>;
}

export interface IdentityConfig {
  project_id: string;
  business_name: string;
  niche: string;
  website?: string;
  schema_type?: string;
  contact?: {
    phone?: string;
    email?: string;
    address?: string;
  };
  socials?: Record<string, string>;
}

export interface BrandBrainConfig {
  voice_tone?: string;
  key_differentiators?: string[];
  knowledge_nuggets?: string[];
  common_objections?: string[];
  forbidden_topics?: string[];
}

export interface TargetingConfig {
  service_focus?: string;
  geo_targets?: {
    cities?: string[];
    suburbs?: string[];
  };
}

export interface CampaignConfig {
  module?: string;
  identity?: IdentityConfig;
  brand_brain?: BrandBrainConfig;
  modules?: {
    lead_gen?: LeadGenModuleConfig;
    local_seo?: { enabled?: boolean };
    pseo?: {
      targeting?: TargetingConfig;
      mining_requirements?: Record<string, unknown>;
      assets?: Array<{ type: string; title?: string; data_source?: string }>;
    };
    admin?: { enabled?: boolean };
    [key: string]: unknown;
  };
  form_settings?: FormSettings;
  sales_bridge?: SalesBridgeConfig;
  targeting?: TargetingConfig;
  [key: string]: unknown;
}
