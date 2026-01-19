"use client";

import useSWR from "swr";
import { getProjects, createProject } from "@/lib/api";
import { getAuthUser } from "@/lib/auth";
import type { Project } from "@/lib/types";

async function fetchProjects(): Promise<Project[]> {
  const user_id = getAuthUser() || "admin";
  
  try {
    const projects = await getProjects(user_id);
    return projects;
  } catch (error) {
    console.error("Error fetching projects:", error);
    return [];
  }
}

export function useProjects() {
  const { data, error, isLoading, mutate } = useSWR<Project[]>(
    "projects",
    fetchProjects,
    {
      refreshInterval: 30000, // Poll every 30 seconds
      revalidateOnFocus: true,
    }
  );

  const createNewProject = async (name: string, niche: string) => {
    const user_id = getAuthUser() || "admin";
    try {
      const result = await createProject(user_id, name, niche);
      // Refresh projects list
      mutate();
      return result;
    } catch (error) {
      console.error("Error creating project:", error);
      throw error;
    }
  };

  return {
    projects: data || [],
    isLoading,
    isError: error,
    mutate,
    createProject: createNewProject,
  };
}
