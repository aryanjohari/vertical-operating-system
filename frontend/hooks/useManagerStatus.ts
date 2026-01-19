"use client";

import useSWR from "swr";
import { runAgent } from "@/lib/api";
import type { ManagerStatus } from "@/lib/types";
import { getAuthUser } from "@/lib/auth";

async function fetchManagerStatus(): Promise<ManagerStatus> {
  const user_id = getAuthUser() || "admin";
  const result = await runAgent("manager", user_id, {});
  return result as ManagerStatus;
}

export function useManagerStatus() {
  const { data, error, isLoading, mutate } = useSWR<ManagerStatus>(
    "manager-status",
    fetchManagerStatus,
    {
      refreshInterval: 10000, // Poll every 10 seconds
      revalidateOnFocus: true,
    }
  );

  return {
    data,
    isLoading,
    isError: error,
    mutate,
  };
}
