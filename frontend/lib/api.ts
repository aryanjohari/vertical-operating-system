/**
 * API Client — Type-safe bridge to FastAPI backend
 * Uses axios singleton with 401 → /login redirect
 */

import axios, { type AxiosInstance } from "axios";
import type { Entity, SeoKeyword, PageDraft, Lead, Project } from "@/types";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Auth token storage (set via setAuthToken after login)
let authToken: string | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
}

export function getAuthToken(): string | null {
  return authToken;
}

// ---------------------------------------------------------------------------
// Axios Instance
// ---------------------------------------------------------------------------

const createClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: API_BASE_URL,
    headers: {
      "Content-Type": "application/json",
    },
  });

  // Request: inject Bearer token
  client.interceptors.request.use((config) => {
    if (authToken) {
      config.headers.Authorization = `Bearer ${authToken}`;
    }
    return config;
  });

  // Response: redirect to /login on 401
  client.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
      }
      return Promise.reject(error);
    }
  );

  return client;
};

const api = createClient();

// ---------------------------------------------------------------------------
// Entity Type Literals
// ---------------------------------------------------------------------------

export type EntityType = "seo_keyword" | "page_draft" | "lead" | string;

// ---------------------------------------------------------------------------
// Auth & Projects
// ---------------------------------------------------------------------------

/**
 * Login. Returns token on success.
 * POST /api/auth/verify
 */
export async function login(
  email: string,
  password: string
): Promise<{ success: boolean; user_id: string | null; token: string | null }> {
  const { data } = await api.post<{
    success: boolean;
    user_id: string | null;
    token: string | null;
  }>("/api/auth/verify", { email, password });
  return data;
}

/**
 * Register a new user.
 * POST /api/auth/register
 * Backend accepts email + password only; fullName/agencyName stored client-side for onboarding.
 */
export async function register(
  email: string,
  password: string,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- optional fullName/agencyName for API shape
  ..._rest: (string | undefined)[]
): Promise<{ success: boolean; user_id: string | null }> {
  const { data } = await api.post<{
    success: boolean;
    user_id: string | null;
  }>("/api/auth/register", { email, password });
  return data;
}

export const auth = {
  login,
  register,
};

/**
 * Fetch all projects for the authenticated user.
 * GET /api/projects
 */
export async function getProjects(): Promise<Project[]> {
  const { data } = await api.get<{ projects: Project[] }>("/api/projects");
  return data.projects ?? [];
}

/**
 * Profile form data matching profile_template.yaml structure.
 */
export interface ProfileFormData {
  identity: {
    project_id: string;
    business_name: string;
    niche: string;
    website: string;
    schema_type: string;
    contact: { phone: string; email: string; address: string };
    socials: { facebook: string; linkedin: string; google_maps_cid: string };
  };
  brand_brain: {
    voice_tone: string;
    key_differentiators: string[] | string;
    knowledge_nuggets: string[] | string;
    common_objections: string[] | string;
    forbidden_topics: string[] | string;
  };
  modules: {
    local_seo: { enabled: boolean };
    lead_gen: { enabled: boolean };
    admin: { enabled: boolean };
  };
}

/**
 * Form schema from YAML (schema-driven forms).
 */
export interface FormSchemaField {
  path: string;
  type: "string" | "array" | "boolean" | "number" | "object";
  itemType?: "string" | "object";
  required?: boolean;
  default?: unknown;
  label?: string;
  /** For array of object: schema for one item (sub-fields with relative paths). */
  itemSchema?: FormSchemaField[];
}

export interface FormSchema {
  fields: FormSchemaField[];
  sections: Record<string, FormSchemaField[]>;
}

export interface FormSchemaResponse {
  schema: FormSchema;
  defaults: Record<string, unknown>;
}

/**
 * Fetch form schema for dynamic forms (YAML-driven).
 * GET /api/schemas/profile | /api/schemas/campaign/pseo | /api/schemas/campaign/lead_gen
 */
export async function getFormSchema(
  type: "profile" | "pseo" | "lead_gen"
): Promise<FormSchemaResponse> {
  const path =
    type === "profile"
      ? "/api/schemas/profile"
      : `/api/schemas/campaign/${type}`;
  const { data } = await api.get<FormSchemaResponse>(path);
  return data;
}

/**
 * Create a new project (simple: name + niche).
 * POST /api/projects
 */
export async function createProject(
  name: string,
  niche: string
): Promise<{ success: boolean; project_id: string }> {
  const { data } = await api.post<{
    success: boolean;
    project_id: string;
    message?: string;
  }>("/api/projects", { name, niche });
  return { success: data.success, project_id: data.project_id };
}

/**
 * Create a new project with full profile form data (schema-driven, matches profile_template.yaml).
 * POST /api/projects
 */
export async function createProjectWithProfile(
  profile: Record<string, unknown>
): Promise<{ success: boolean; project_id: string }> {
  const { data } = await api.post<{
    success: boolean;
    project_id: string;
    message?: string;
  }>("/api/projects", { profile });
  return { success: data.success, project_id: data.project_id };
}

/**
 * Fetch a single project by ID.
 * Resolves from getProjects() since backend has no dedicated endpoint.
 */
export async function getProject(projectId: string): Promise<Project | null> {
  const projects = await getProjects();
  return projects.find((p) => p.project_id === projectId) ?? null;
}

/**
 * Fetch project DNA/config.
 * GET /api/projects/{projectId}/dna
 */
export async function getProjectConfig(
  projectId: string
): Promise<Record<string, unknown>> {
  const { data } = await api.get<{ config: Record<string, unknown> }>(
    `/api/projects/${projectId}/dna`
  );
  return data.config ?? {};
}

/**
 * Update project DNA/config.
 * PUT /api/projects/{projectId}/dna
 */
export async function updateProjectConfig(
  projectId: string,
  config: Record<string, unknown>
): Promise<{ success: boolean }> {
  const { data } = await api.put<{ success: boolean }>(
    `/api/projects/${projectId}/dna`,
    config
  );
  return data;
}

/**
 * Get WordPress/CMS credentials (password never returned).
 * GET /api/settings
 */
export async function getSettings(): Promise<{
  wp_url: string;
  wp_user: string;
  wp_password: string;
}> {
  const { data } = await api.get<{
    wp_url: string;
    wp_user: string;
    wp_password: string;
  }>("/api/settings");
  return data ?? { wp_url: "", wp_user: "", wp_password: "" };
}

/**
 * Save WordPress/CMS credentials. Omit or leave wp_password empty to keep existing password.
 * POST /api/settings
 */
export async function saveSettings(credentials: {
  wp_url: string;
  wp_user: string;
  wp_password?: string;
}): Promise<{ success: boolean; message: string }> {
  const { data } = await api.post<{ success: boolean; message: string }>(
    "/api/settings",
    {
      wp_url: credentials.wp_url ?? "",
      wp_user: credentials.wp_user ?? "",
      wp_password: credentials.wp_password ?? "",
    }
  );
  return data;
}

// ---------------------------------------------------------------------------
// API Methods
// ---------------------------------------------------------------------------

/**
 * Fetch entities filtered by type and optional project.
 * GET /api/entities?entity_type=...&project_id=...&limit=...&offset=...&campaign_id=...
 */
export async function getEntities<T extends Entity = Entity>(
  type: EntityType,
  projectId?: string | null,
  opts?: { campaignId?: string; limit?: number; offset?: number }
): Promise<T[]> {
  const params: Record<string, string | number> = { entity_type: type };
  if (projectId) params.project_id = projectId;
  if (opts?.campaignId) params.campaign_id = opts.campaignId;
  if (opts?.limit != null) params.limit = opts.limit;
  if (opts?.offset != null) params.offset = opts.offset;

  const { data } = await api.get<{ entities: T[] }>("/api/entities", {
    params,
  });
  return data.entities ?? [];
}

/**
 * Fetch page drafts for a campaign with pagination. Returns entities and total count.
 */
export async function getCampaignDrafts(
  projectId: string,
  campaignId: string,
  page: number = 1,
  pageSize: number = 20
): Promise<{ entities: PageDraft[]; total: number }> {
  const offset = (page - 1) * pageSize;
  const params: Record<string, string | number> = {
    entity_type: "page_draft",
    project_id: projectId,
    campaign_id: campaignId,
    limit: pageSize,
    offset,
  };
  const { data } = await api.get<{ entities: PageDraft[]; total?: number }>(
    "/api/entities",
    { params }
  );
  return {
    entities: data.entities ?? [],
    total: data.total ?? data.entities?.length ?? 0,
  };
}

/**
 * Update an entity's metadata.
 * PUT /api/entities/{entity_id}
 */
export async function updateEntity(
  entityId: string,
  metadata: Record<string, unknown>
): Promise<{ success: boolean }> {
  const { data } = await api.put<{ success: boolean }>(
    `/api/entities/${entityId}`,
    { metadata }
  );
  return data;
}

/**
 * Delete an entity.
 * DELETE /api/entities/{entity_id}
 */
export async function deleteEntity(
  entityId: string
): Promise<{ success: boolean }> {
  const { data } = await api.delete<{ success: boolean }>(
    `/api/entities/${entityId}`
  );
  return data;
}

/**
 * Create a new entity.
 * POST /api/entities
 */
export async function createEntity<
  T extends Record<string, unknown> = Record<string, unknown>
>(
  type: EntityType,
  data: {
    name: string;
    primary_contact?: string | null;
    metadata?: Record<string, unknown>;
    project_id?: string | null;
  }
): Promise<{ success: boolean; entity: T & Entity }> {
  const { data: response } = await api.post<{
    success: boolean;
    entity: T & Entity;
  }>("/api/entities", {
    entity_type: type,
    name: data.name,
    primary_contact: data.primary_contact ?? null,
    metadata: data.metadata ?? {},
    project_id: data.project_id ?? null,
  });
  return response;
}

/**
 * Fetch campaigns for a project.
 * GET /api/projects/{projectId}/campaigns?module=...
 */
export async function getCampaigns(
  projectId: string,
  module?: string
): Promise<
  {
    id: string;
    name: string;
    module: string;
    status: string;
    config?: Record<string, unknown>;
  }[]
> {
  const params: Record<string, string> = {};
  if (module) params.module = module;
  const { data } = await api.get<{
    campaigns: {
      id: string;
      name: string;
      module: string;
      status: string;
      config?: Record<string, unknown>;
    }[];
  }>(`/api/projects/${projectId}/campaigns`, { params });
  return data.campaigns ?? [];
}

export type Campaign = {
  id: string;
  name: string;
  module: string;
  status: string;
  config?: Record<string, unknown>;
  project_id?: string;
  stats?: Record<string, unknown>;
};

/**
 * Fetch a single campaign by ID with full config.
 * GET /api/projects/{projectId}/campaigns/{campaignId}
 */
export async function getCampaign(
  projectId: string,
  campaignId: string
): Promise<Campaign> {
  const { data } = await api.get<{ campaign: Campaign }>(
    `/api/projects/${projectId}/campaigns/${campaignId}`
  );
  return data.campaign;
}

/**
 * Update campaign config. Full replace with config, or shallow merge with config_partial.
 * PATCH /api/projects/{projectId}/campaigns/{campaignId}
 */
export async function updateCampaignConfig(
  projectId: string,
  campaignId: string,
  config: Record<string, unknown>,
  options?: { merge?: boolean }
): Promise<Campaign> {
  const body = options?.merge
    ? { config_partial: config }
    : { config };
  const { data } = await api.patch<{ campaign: Campaign }>(
    `/api/projects/${projectId}/campaigns/${campaignId}`,
    body
  );
  return data.campaign;
}

/**
 * Create a campaign via form data (1:1 mapping to pseo_default or lead_gen_default).
 * POST /api/projects/{projectId}/campaigns
 */
export async function createCampaignWithForm(
  projectId: string,
  module: "pseo" | "lead_gen",
  formData: Record<string, unknown>,
  name?: string
): Promise<{ campaign_id: string }> {
  const { data } = await api.post<{ campaign_id: string }>(
    `/api/projects/${projectId}/campaigns`,
    { name: name ?? "", module, form_data: formData }
  );
  return { campaign_id: data.campaign_id };
}

/**
 * Dispatch an agent task (e.g. scrape_leads, write_blog, sales_agent).
 * POST /api/run
 */
export async function dispatchTask(
  taskName: string,
  params: Record<string, unknown> = {}
): Promise<{
  status: string;
  data: unknown;
  message: string;
  timestamp?: string;
}> {
  const { data } = await api.post<{
    status: string;
    data: unknown;
    message: string;
    timestamp?: string;
  }>("/api/run", {
    task: taskName,
    params,
  });

  return data;
}

/**
 * pSEO: get pipeline stats and recommended next step.
 * Dispatches manager with action dashboard_stats.
 */
export async function getPseoStats(
  projectId: string,
  campaignId: string
): Promise<{
  stats: Record<string, unknown>;
  next_step: {
    agent_key: string | null;
    label: string;
    description: string;
    reason: string;
  };
}> {
  const res = await dispatchTask("manager", {
    action: "dashboard_stats",
    project_id: projectId,
    campaign_id: campaignId,
  });
  const data = (res.data as Record<string, unknown>) ?? {};
  return {
    stats: (data.stats as Record<string, unknown>) ?? {},
    next_step: (data.next_step as {
      agent_key: string | null;
      label: string;
      description: string;
      reason: string;
    }) ?? {
      agent_key: null,
      label: "—",
      description: "",
      reason: "",
    },
  };
}

/**
 * pSEO: run a single pipeline step (e.g. scout_anchors, write_pages).
 * Returns result and next_step. On error, show message and freeze (no auto-continue).
 * Optional params (e.g. keyword_id) are forwarded to the manager/agent for manual page creation.
 */
export async function runPseoStep(
  projectId: string,
  campaignId: string,
  step: string,
  params?: Record<string, unknown>
): Promise<{
  status: string;
  message: string;
  data?: {
    step: string;
    next_step: {
      agent_key: string | null;
      label: string;
      description: string;
      reason: string;
    };
    stats?: Record<string, unknown>;
  };
}> {
  const res = await dispatchTask("manager", {
    action: "run_step",
    step,
    project_id: projectId,
    campaign_id: campaignId,
    ...params,
  });
  return {
    status: res.status,
    message: res.message,
    data: res.data as {
      step: string;
      next_step: {
        agent_key: string | null;
        label: string;
        description: string;
        reason: string;
      };
      stats?: Record<string, unknown>;
    },
  };
}

/**
 * pSEO: run the next pipeline step for a specific draft (phase-based row control).
 * Dispatches manager with action run_next_for_draft and draft_id.
 */
export async function runNextForDraft(
  projectId: string,
  campaignId: string,
  draftId: string
): Promise<{
  status: string;
  message: string;
  data?: {
    draft_id: string;
    step: string | null;
    result?: unknown;
    next_step?: string | null;
  };
}> {
  const res = await dispatchTask("manager", {
    action: "run_next_for_draft",
    draft_id: draftId,
    project_id: projectId,
    campaign_id: campaignId,
  });
  return {
    status: res.status,
    message: res.message,
    data: res.data as {
      draft_id: string;
      step: string | null;
      result?: unknown;
      next_step?: string | null;
    },
  };
}

/**
 * Lead gen: run the next step for a specific lead (phase-based row control).
 * Dispatches lead_gen_manager with action run_next_for_lead and lead_id.
 */
export async function runNextForLead(
  projectId: string,
  campaignId: string,
  leadId: string
): Promise<{
  status: string;
  message: string;
  data?: {
    lead_id: string;
    next_step?: { action: string; label: string } | null;
    result?: unknown;
  };
}> {
  const res = await dispatchTask("lead_gen_manager", {
    action: "run_next_for_lead",
    lead_id: leadId,
    project_id: projectId,
    campaign_id: campaignId,
  });
  return {
    status: res.status,
    message: res.message,
    data: res.data as {
      lead_id: string;
      next_step?: { action: string; label: string } | null;
      result?: unknown;
    },
  };
}

/**
 * Initiate Sales Bridge call for a lead.
 * Dispatches sales_agent with action "instant_call" — rings the boss, whisper,
 * then connects to customer when boss presses 1.
 */
export async function connectCall(
  leadId: string,
  projectId: string
): Promise<{
  status: string;
  data?: { call_sid?: string };
  message: string;
}> {
  return dispatchTask("sales_agent", {
    action: "instant_call",
    lead_id: leadId,
    project_id: projectId,
  }) as Promise<{
    status: string;
    data?: { call_sid?: string };
    message: string;
  }>;
}

// ---------------------------------------------------------------------------
// Typed Convenience Helpers (optional)
// ---------------------------------------------------------------------------

export const entities = {
  getKeywords: (projectId?: string | null) =>
    getEntities<SeoKeyword>("seo_keyword", projectId),
  getPageDrafts: (projectId?: string | null) =>
    getEntities<PageDraft>("page_draft", projectId),
  getLeads: (projectId?: string | null) => getEntities<Lead>("lead", projectId),
};

// ---------------------------------------------------------------------------
// Export singleton for custom usage
// ---------------------------------------------------------------------------

export default api;
