// lib/types.ts
export interface AgentInput {
  task: string;
  user_id: string;
  params: Record<string, any>;
  request_id?: string;
}

export interface AgentOutput {
  status: 'success' | 'error' | 'complete' | 'warning' | 'skipped' | 'processing';
  data: any;
  message: string;
  timestamp: string;
  error_details?: any;
  context_id?: string;
}

export interface ProcessingResponse {
  status: 'processing';
  data: {
    context_id: string;
    task: string;
  };
  message: string;
  timestamp: string;
}

export interface AgentContext {
  context_id: string;
  project_id: string;
  user_id: string;
  created_at: string;
  expires_at: string;
  data: {
    request_id?: string;
    task?: string;
    status?: 'processing' | 'completed' | 'failed';
    result?: AgentOutput;
  };
}

export interface Entity {
  id: string;
  tenant_id: string;
  project_id?: string;
  entity_type: string;
  name: string;
  primary_contact?: string;
  metadata: Record<string, any>;
  created_at: string;
}

export interface Project {
  project_id: string;
  user_id: string;
  niche: string;
  dna_path?: string;
  created_at: string;
}

export interface DNAConfig {
  identity: {
    project_id: string;
    business_name: string;
    niche: string;
    website: string;
    schema_type?: string;
    contact: {
      phone: string;
      email: string;
      address: string;
    };
    services?: Array<{
      name: string;
      slug: string;
      primary_keywords: string[];
      context_keywords: string[];
    }>;
  };
  brand_brain: {
    voice_tone: string;
    key_differentiators: string[];
    insider_tips: string[];
    common_objections: string[];
    forbidden_topics: string[];
  };
  modules: {
    local_seo?: {
      enabled: boolean;
      scout_settings: {
        anchor_entities: string[];
        geo_scope: {
          cities: string[];
        };
      };
      publisher_settings: {
        cms: string;
        url: string;
        username: string;
      };
      seo_rules?: {
        force_schema_injection?: boolean;
        force_meta_description?: boolean;
        structure?: {
          title_format?: string;
        };
      };
    };
    lead_gen?: {
      enabled: boolean;
      voice_agent: {
        forwarding_number: string;
        greeting: string;
      };
      tools: {
        lead_magnets: string[];
      };
    };
  };
}

export interface AuthResponse {
  success: boolean;
  user_id?: string;
  token?: string;
}

export interface Settings {
  wp_url: string;
  wp_user: string;
  wp_password: string;
}

export interface PipelineStats {
  anchors: number;
  kws_total: number;
  kws_pending: number;
  '1_unreviewed': number;
  '2_validated': number;
  '3_linked': number;
  '4_imaged': number;
  '5_ready': number;
  '6_live': number;
}

export interface NextStep {
  agent_key: string | null;
  label: string;
  description: string;
  reason: string;
}

export interface LeadGenStats {
  total_leads: number;
  avg_lead_score: number;
  total_pipeline_value: number;
  conversion_rate: number;
  sources: {
    sniper: number;
    web: number;
    voice: number;
    google_ads: number;
    wordpress_form: number;
  };
  priorities: {
    high: number;
    medium: number;
    low: number;
  };
  recent_leads: string[];
}
