import axios from "axios";
import type { AgentInput, AgentOutput, HealthStatus, Entity, Project } from "./types";
import { getAuthUser } from "./auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export async function runAgent(
  task: string,
  user_id: string,
  params: Record<string, any> = {}
): Promise<AgentOutput> {
  const payload: AgentInput = {
    task,
    user_id,
    params,
  };

  const response = await apiClient.post<AgentOutput>("/api/run", payload);
  return response.data;
}

export async function healthCheck(): Promise<HealthStatus> {
  const response = await apiClient.get<HealthStatus>("/");
  return response.data;
}

// Verify user credentials against SQL database
export interface AuthRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  success: boolean;
  user_id: string | null;
}

export async function verifyUser(
  email: string,
  password: string
): Promise<{ success: boolean; user_id: string | null }> {
  try {
    const response = await apiClient.post<AuthResponse>("/api/auth/verify", {
      email,
      password,
    });
    // Debug: log the response to see what we're getting
    console.log("Auth response:", response.data);
    return response.data;
  } catch (error) {
    console.error("Auth verification error:", error);
    return { success: false, user_id: null };
  }
}

export async function registerUser(
  email: string,
  password: string
): Promise<{ success: boolean; user_id: string | null }> {
  try {
    const response = await apiClient.post<AuthResponse>("/api/auth/register", {
      email,
      password,
    });
    return response.data;
  } catch (error) {
    console.error("Registration error:", error);
    return { success: false, user_id: null };
  }
}

// Get entities from backend
export interface EntitiesResponse {
  entities: Entity[];
}

export async function getEntities(
  user_id: string,
  entity_type?: string,
  project_id?: string
): Promise<Entity[]> {
  try {
    const params = new URLSearchParams({ user_id });
    if (entity_type) {
      params.append("entity_type", entity_type);
    }
    if (project_id) {
      params.append("project_id", project_id);
    }
    const response = await apiClient.get<EntitiesResponse>(
      `/api/entities?${params.toString()}`
    );
    return response.data.entities;
  } catch (error) {
    console.error("Error fetching entities:", error);
    return [];
  }
}

// Get leads from backend
export interface LeadsResponse {
  leads: Entity[];
}

export async function getLeads(user_id: string): Promise<Entity[]> {
  try {
    const response = await apiClient.get<LeadsResponse>(
      `/api/leads?user_id=${encodeURIComponent(user_id)}`
    );
    return response.data.leads;
  } catch (error) {
    console.error("Error fetching leads:", error);
    return [];
  }
}

// Projects API
export interface ProjectInput {
  user_id: string;
  name: string;
  niche: string;
}

export interface ProjectResponse {
  success: boolean;
  project_id: string;
  message: string;
}

export interface ProjectsResponse {
  projects: Project[];
}

export async function createProject(
  user_id: string,
  name: string,
  niche: string
): Promise<ProjectResponse> {
  try {
    const response = await apiClient.post<ProjectResponse>("/api/projects", {
      user_id,
      name,
      niche,
    });
    return response.data;
  } catch (error) {
    console.error("Error creating project:", error);
    throw error;
  }
}

export async function getProjects(user_id: string): Promise<Project[]> {
  try {
    const response = await apiClient.get<ProjectsResponse>(
      `/api/projects?user_id=${encodeURIComponent(user_id)}`
    );
    return response.data.projects;
  } catch (error) {
    console.error("Error fetching projects:", error);
    return [];
  }
}

// Onboarding API functions
export async function analyzeBusinessUrl(
  user_id: string,
  url: string
): Promise<AgentOutput> {
  try {
    return await runAgent("onboarding", user_id, {
      step: "analyze",
      url,
    });
  } catch (error) {
    console.error("Error analyzing business URL:", error);
    throw error;
  }
}

export async function startOnboardingInterview(
  user_id: string,
  identity: Record<string, any>,
  modules: string[]
): Promise<AgentOutput> {
  try {
    return await runAgent("onboarding", user_id, {
      step: "interview_start",
      identity,
      modules,
    });
  } catch (error) {
    console.error("Error starting onboarding interview:", error);
    throw error;
  }
}

export async function continueOnboardingInterview(
  user_id: string,
  history: Array<{ role: string; content: string }>,
  message: string,
  context: Record<string, any>
): Promise<AgentOutput> {
  try {
    return await runAgent("onboarding", user_id, {
      step: "interview_loop",
      history,
      message,
      context,
    });
  } catch (error) {
    console.error("Error continuing onboarding interview:", error);
    throw error;
  }
}

// Dashboard API functions
export async function runCycle(user_id: string): Promise<AgentOutput> {
  try {
    return await runAgent("manager", user_id, {});
  } catch (error) {
    console.error("Error running cycle:", error);
    throw error;
  }
}

export interface StatsResponse {
  stats: {
    Locations: number;
    Keywords: number;
    Drafts: number;
    "5_ready": number;
    [key: string]: any;
  };
}

export async function getStats(user_id: string): Promise<StatsResponse["stats"]> {
  try {
    const response = await runAgent("manager", user_id, {});
    return response.data?.stats || {
      Locations: 0,
      Keywords: 0,
      Drafts: 0,
      "5_ready": 0,
    };
  } catch (error) {
    console.error("Error fetching stats:", error);
    return {
      Locations: 0,
      Keywords: 0,
      Drafts: 0,
      "5_ready": 0,
    };
  }
}

export async function getPageDrafts(
  user_id: string,
  project_id?: string
): Promise<Entity[]> {
  try {
    return await getEntities(user_id, "page_draft", project_id);
  } catch (error) {
    console.error("Error fetching page drafts:", error);
    return [];
  }
}

export async function deletePage(pageId: string, user_id: string): Promise<boolean> {
  try {
    const response = await apiClient.delete(`/api/entities/${pageId}`, {
      params: { user_id },
    });
    return response.data.success === true;
  } catch (error) {
    console.error("Error deleting page:", error);
    return false;
  }
}

// Entity CRUD functions
export interface CreateEntityInput {
  name: string;
  primary_contact?: string;
  metadata?: Record<string, any>;
  project_id?: string;
}

export async function createEntity(
  user_id: string,
  entity_type: string,
  data: CreateEntityInput
): Promise<Entity | null> {
  try {
    const response = await apiClient.post<{ success: boolean; entity: Entity }>("/api/entities", {
      user_id,
      entity_type,
      name: data.name,
      primary_contact: data.primary_contact,
      metadata: data.metadata || {},
      project_id: data.project_id,
    });
    return response.data.entity;
  } catch (error) {
    console.error("Error creating entity:", error);
    throw error;
  }
}

export interface UpdateEntityInput {
  name?: string;
  primary_contact?: string;
  metadata?: Record<string, any>;
}

export async function updateEntity(
  entityId: string,
  data: UpdateEntityInput
): Promise<boolean> {
  try {
    const user_id = getAuthUser() || "admin";
    const response = await apiClient.put<{ success: boolean }>(
      `/api/entities/${entityId}`,
      {
        name: data.name,
        primary_contact: data.primary_contact,
        metadata: data.metadata,
      },
      {
        params: { user_id },
      }
    );
    return response.data.success === true;
  } catch (error) {
    console.error("Error updating entity:", error);
    throw error;
  }
}

export async function deleteEntity(entityId: string, user_id: string): Promise<boolean> {
  try {
    const response = await apiClient.delete<{ success: boolean }>(
      `/api/entities/${entityId}`,
      {
        params: { user_id },
      }
    );
    return response.data.success === true;
  } catch (error) {
    console.error("Error deleting entity:", error);
    return false;
  }
}

// Settings functions
export interface SettingsData {
  wp_url: string;
  wp_user: string;
  wp_password: string;
}

export async function getSettings(user_id: string): Promise<SettingsData> {
  try {
    const response = await apiClient.get<SettingsData>("/api/settings", {
      params: { user_id },
    });
    return response.data;
  } catch (error) {
    console.error("Error fetching settings:", error);
    return {
      wp_url: "",
      wp_user: "",
      wp_password: "",
    };
  }
}

export async function saveSettings(user_id: string, settings: SettingsData): Promise<boolean> {
  try {
    const response = await apiClient.post<{ success: boolean }>("/api/settings", {
      user_id,
      ...settings,
    });
    return response.data.success === true;
  } catch (error) {
    console.error("Error saving settings:", error);
    throw error;
  }
}
