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

export interface Project {
  project_id: string;
  user_id: string;
  niche: string;
  dna_path?: string;
  created_at?: string;
}
