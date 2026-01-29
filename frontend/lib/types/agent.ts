/**
 * Agent types mirroring backend Pydantic models.
 */

export interface AgentInput {
  task: string;
  user_id: string;
  params: Record<string, unknown>;
  request_id?: string;
}

export type AgentStatus =
  | "success"
  | "error"
  | "complete"
  | "warning"
  | "skipped"
  | "processing";

export interface AgentOutput {
  status: AgentStatus;
  data: unknown;
  message: string;
  timestamp: string;
  error_details?: unknown;
  context_id?: string;
}

export interface ProcessingResponse {
  status: "processing";
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
    status?: "processing" | "completed" | "failed";
    result?: AgentOutput;
  };
}

/** Params for scout_anchors task */
export interface ScoutParams {
  project_id: string;
  campaign_id: string;
}

/** Params for write_pages task */
export interface WriterParams {
  project_id: string;
  campaign_id: string;
}

/** Params for sniper_agent task */
export interface SniperParams {
  project_id: string;
  campaign_id: string;
}
