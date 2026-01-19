"use client";

import useSWR from "swr";
import { getLeads } from "@/lib/api";
import type { Entity } from "@/lib/types";
import { getAuthUser } from "@/lib/auth";

async function fetchLeads(): Promise<Entity[]> {
  const user_id = getAuthUser() || "admin";
  
  try {
    const leads = await getLeads(user_id);
    return leads;
  } catch (error) {
    console.error("Error fetching leads:", error);
    return [];
  }
}

export function useLeads() {
  const { data, error, isLoading, mutate } = useSWR<Entity[]>(
    "leads",
    fetchLeads,
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
