"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { getProject, getCampaigns } from "@/lib/api";
import type { Project } from "@/types";
import { Plus, Rocket, Users } from "lucide-react";
import { CreateCampaignDialog } from "@/components/campaigns/CreateCampaignDialog";

type Campaign = {
  id: string;
  name: string;
  module: string;
  status: string;
};

export default function ProjectDashboardPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params.projectId as string;

  const [project, setProject] = useState<Project | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [createModule, setCreateModule] = useState<"pseo" | "lead_gen" | null>(null);

  const loadData = useCallback(async () => {
    if (!projectId) return;
    try {
      const [proj, campList] = await Promise.all([
        getProject(projectId),
        getCampaigns(projectId),
      ]);
      setProject(proj ?? null);
      setCampaigns(campList);
    } catch {
      setProject(null);
      setCampaigns([]);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreateClick = (module: "pseo" | "lead_gen") => {
    setCreateModule(module);
    setCreateDialogOpen(true);
  };

  const handleCreateSuccess = () => {
    setCreateDialogOpen(false);
    setCreateModule(null);
    loadData();
  };

  const pseoCampaigns = campaigns.filter((c) => c.module === "pseo");
  const leadGenCampaigns = campaigns.filter((c) => c.module === "lead_gen");
  const displayName =
    project?.niche || projectId?.replace(/_/g, " ") || "Project";

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-64 animate-pulse rounded bg-muted" />
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="h-40 animate-pulse rounded-lg bg-muted" />
          <div className="h-40 animate-pulse rounded-lg bg-muted" />
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="glass-panel p-12 text-center">
        <p className="text-muted-foreground">Project not found.</p>
        <button
          type="button"
          onClick={() => router.push("/projects")}
          className="mt-4 text-secondary hover:underline"
        >
          Back to Projects
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="acid-text text-2xl font-bold text-foreground">
        {displayName.charAt(0).toUpperCase() + displayName.slice(1)}
      </h1>

      {/* pSEO block */}
      <section className="glass-panel rounded-lg border border-border p-4">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
            <Rocket className="h-5 w-5" />
            pSEO Campaigns
          </h2>
          <button
            type="button"
            onClick={() => handleCreateClick("pseo")}
            className="acid-glow flex items-center gap-2 rounded bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            Create Campaign
          </button>
        </div>
        {pseoCampaigns.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">
            No pSEO campaigns yet. Create one to get started.
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {pseoCampaigns.map((c) => (
              <li
                key={c.id}
                className="flex items-center justify-between rounded border border-border bg-muted/30 px-3 py-2 text-sm"
              >
                <Link
                  href={`/projects/${projectId}/campaigns/${c.id}`}
                  className="font-medium text-foreground hover:underline"
                >
                  {c.name}
                </Link>
                <span className="text-xs text-muted-foreground">{c.status}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Lead Gen block */}
      <section className="glass-panel rounded-lg border border-border p-4">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
            <Users className="h-5 w-5" />
            Lead Gen Campaigns
          </h2>
          <button
            type="button"
            onClick={() => handleCreateClick("lead_gen")}
            className="acid-glow flex items-center gap-2 rounded bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            Create Campaign
          </button>
        </div>
        {leadGenCampaigns.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">
            No Lead Gen campaigns yet. Create one to get started.
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {leadGenCampaigns.map((c) => (
              <li
                key={c.id}
                className="flex items-center justify-between rounded border border-border bg-muted/30 px-3 py-2 text-sm"
              >
                <Link
                  href={`/projects/${projectId}/campaigns/${c.id}`}
                  className="font-medium text-foreground hover:underline"
                >
                  {c.name}
                </Link>
                <span className="text-xs text-muted-foreground">{c.status}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <CreateCampaignDialog
        isOpen={createDialogOpen}
        onClose={() => {
          setCreateDialogOpen(false);
          setCreateModule(null);
        }}
        onSuccess={handleCreateSuccess}
        projectId={projectId}
        module={createModule ?? "pseo"}
      />
    </div>
  );
}
