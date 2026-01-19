"use client";

import useSWR from "swr";
import { getEntities } from "@/lib/api";
import type { Entity } from "@/lib/types";
import { getAuthUser } from "@/lib/auth";

async function fetchLeads(projectId: string | null): Promise<Entity[]> {
  const user_id = getAuthUser() || "admin";
  
  try {
    const leads = await getEntities(user_id, "lead", projectId || undefined);
    return leads;
  } catch (error) {
    console.error("Error fetching leads:", error);
    return [];
  }
}

export function useLeads(projectId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<Entity[]>(
    projectId ? `leads-${projectId}` : "leads",
    () => fetchLeads(projectId),
    {
      refreshInterval: 10000, // Poll every 10 seconds
      revalidateOnFocus: true,
    }
  );

  return {
    leads: data || [],
    isLoading,
    isError: error,
    mutate,
  };
}
