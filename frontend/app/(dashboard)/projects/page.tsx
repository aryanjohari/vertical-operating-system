"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getProjects, getEntities } from "@/lib/api";
import type { Project } from "@/types";
import { ProjectCard } from "@/components/projects/ProjectCard";
import { ProjectCardSkeleton } from "@/components/projects/ProjectCardSkeleton";
import { Plus } from "lucide-react";

export default function AllProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<(Project & { leadCount: number })[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const projectsData = await getProjects();
        const leadCounts = await Promise.all(
          projectsData.map(async (p) => {
            const leads = await getEntities("lead", p.project_id);
            return { projectId: p.project_id, count: leads.length };
          })
        );
        const countMap = Object.fromEntries(
          leadCounts.map((c) => [c.projectId, c.count])
        );
        setProjects(
          projectsData.map((p) => ({
            ...p,
            leadCount: countMap[p.project_id] ?? 0,
          }))
        );
      } catch {
        setProjects([]);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="acid-text text-2xl font-bold text-foreground">
          All Projects
        </h1>
        <button
          type="button"
          onClick={() => router.push("/onboarding")}
          className="acid-glow flex items-center gap-2 rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          New Project
        </button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {loading ? (
          <>
            <ProjectCardSkeleton />
            <ProjectCardSkeleton />
            <ProjectCardSkeleton />
          </>
        ) : projects.length === 0 ? (
          <div className="col-span-full glass-panel p-12 text-center">
            <p className="text-muted-foreground">No projects yet.</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Create your first project to get started.
            </p>
            <button
              type="button"
              onClick={() => router.push("/onboarding")}
              className="mt-4 text-secondary hover:underline"
            >
              Go to Onboarding
            </button>
          </div>
        ) : (
          projects.map((project) => (
            <ProjectCard
              key={project.project_id}
              project={project}
              leadCount={project.leadCount}
            />
          ))
        )}
      </div>
    </div>
  );
}
