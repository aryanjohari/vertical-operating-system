/**
 * API Client — Type-safe bridge to FastAPI backend
 * Uses axios singleton with 401 → /login redirect
 */

import axios, { type AxiosInstance } from "axios";
import type {
  Entity,
  SeoKeyword,
  PageDraft,
  Lead,
  Project,
} from "@/types";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  _fullName?: string,
  _agencyName?: string
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

// ---------------------------------------------------------------------------
// API Methods
// ---------------------------------------------------------------------------

/**
 * Fetch entities filtered by type and optional project.
 * GET /api/entities?entity_type=...&project_id=...
 */
export async function getEntities<T extends Entity = Entity>(
  type: EntityType,
  projectId?: string | null
): Promise<T[]> {
  const params: Record<string, string> = { entity_type: type };
  if (projectId) params.project_id = projectId;

  const { data } = await api.get<{ entities: T[] }>("/api/entities", {
    params,
  });
  return data.entities ?? [];
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
  T extends Record<string, unknown> = Record<string, unknown>,
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
  getLeads: (projectId?: string | null) =>
    getEntities<Lead>("lead", projectId),
};

// ---------------------------------------------------------------------------
// Export singleton for custom usage
// ---------------------------------------------------------------------------

export default api;
