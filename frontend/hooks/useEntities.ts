"use client";

import useSWR from "swr";
import { getEntities } from "@/lib/api";
import type { Entity } from "@/lib/types";
import { getAuthUser } from "@/lib/auth";

async function fetchEntities(entityType: string): Promise<Entity[]> {
  const user_id = getAuthUser() || "admin";
  
  try {
    const entities = await getEntities(user_id, entityType);
    return entities;
  } catch (error) {
    console.error("Error fetching entities:", error);
    return [];
  }
}

export function useEntities(entityType: string) {
  const { data, error, isLoading, mutate } = useSWR<Entity[]>(
    entityType ? `entities-${entityType}` : null,
    () => fetchEntities(entityType),
    {
      refreshInterval: 10000, // Poll every 10 seconds
      revalidateOnFocus: true,
    }
  );

  return {
    entities: data || [],
    isLoading,
    isError: error,
    mutate,
  };
}
