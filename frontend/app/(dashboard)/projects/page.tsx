"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getProjects } from "@/lib/api";
import type { Project } from "@/types";
import { ProjectCardSkeleton } from "@/components/projects/ProjectCardSkeleton";
import { CreateProjectDialog } from "@/components/projects/CreateProjectDialog";
import { Plus } from "lucide-react";
import { cn } from "@/lib/utils";

function ProjectRow({ project }: { project: Project }) {
  const name = project.niche || project.project_id;
  const displayName =
    name.charAt(0).toUpperCase() + name.replace(/_/g, " ").slice(1);

  return (
    <Link href={`/projects/${project.project_id}`}>
      <div
        className="glass-panel flex flex-col gap-2 rounded-lg border border-border p-6 transition-colors hover:border-primary/40 hover:shadow-[0_0_20px_2px_hsl(0_100%_60%/0.08)]"
        role="row"
      >
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-foreground">{displayName}</h3>
          <span
            className={cn(
              "inline-flex rounded px-2 py-0.5 text-xs font-medium",
              "bg-primary/20 text-primary"
            )}
          >
            Active
          </span>
        </div>
        <p className="text-sm text-muted-foreground">{project.project_id}</p>
      </div>
    </Link>
  );
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);

  const loadProjects = useCallback(async () => {
    try {
      const data = await getProjects();
      setProjects(data);
    } catch {
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-foreground">Projects</h2>
        <button
          type="button"
          onClick={() => setDialogOpen(true)}
          className="acid-glow flex items-center gap-2 rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          Create New Project
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
          </div>
        ) : (
          projects.map((project) => (
            <ProjectRow key={project.project_id} project={project} />
          ))
        )}
      </div>
      <CreateProjectDialog
        isOpen={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSuccess={loadProjects}
      />
    </div>
  );
}
