// TypeScript interfaces matching backend models

export interface AgentInput {
  task: string;
  user_id: string;
  params: Record<string, any>;
  request_id?: string;
}

export interface AgentOutput {
  status: "success" | "error" | "action_required" | "complete" | "continue";
  data: any;
  message: string;
  timestamp: string;
}

export interface HealthStatus {
  status: string;
  system: string;
  version: string;
  loaded_agents: string[];
}

export interface Entity {
  id?: string;
  tenant_id?: string;
  entity_type?: string;
  name: string;
  primary_contact?: string;
  metadata: Record<string, any>;
  created_at?: string;
}

export interface ManagerStats {
  Locations: number;
  Keywords: number;
  Drafts: number;
  "Enhanced (Img)": number;
  "Interactive (JS)": number;
  Live: number;
  // Pipeline stage counts
  "1_unreviewed": number;
  "2_validated": number;
  "3_linked": number;
  "4_imaged": number;
  "5_ready": number;
  "6_live": number;
  kws_pending?: number;
}

export interface PipelineStage {
  id: string;
  name: string;
  icon: string;
  count: number;
  status: "complete" | "active" | "attention" | "pending";
}

export interface ManagerStatus {
  status: string;
  message: string;
  data: {
    step?: string;
    stats: ManagerStats;
    description?: string;
    action_label?: string;
    next_task?: string;
    next_params?: Record<string, any>;
  };
}

export interface Draft extends Entity {
  metadata: {
    status?: string;
    quality_score?: number;
    critic_notes?: string;
    featured_image?: string;
    content?: string;
    [key: string]: any;
  };
}

export interface Project {
  project_id: string;
  user_id: string;
  niche: string;
  dna_path?: string;
  created_at?: string;
}

export interface BusinessIdentity {
  business_name: string;
  niche: string;
  phone?: string;
  email?: string;
  address?: string;
  website: string;
  key_services?: string[];
  project_id?: string;
}

export interface OnboardingContext {
  identity: BusinessIdentity;
  modules: string[];
}
