import axios from "axios";
import type { AgentInput, AgentOutput, HealthStatus, Entity } from "./types";

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

// Get entities from backend
export interface EntitiesResponse {
  entities: Entity[];
}

export async function getEntities(
  user_id: string,
  entity_type?: string
): Promise<Entity[]> {
  try {
    const params = new URLSearchParams({ user_id });
    if (entity_type) {
      params.append("entity_type", entity_type);
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
