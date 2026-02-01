"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import {
  getProject,
  getEntities,
} from "@/lib/api";
import type { Project } from "@/types";
import type { PageDraft, Lead } from "@/types";
import { PulseCard, PulseCardSkeleton } from "@/components/projects/PulseCard";
import { Rocket, Users, Dna } from "lucide-react";

export default function ProjectOverviewPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params.projectId as string;

  const [project, setProject] = useState<Project | null>(null);
  const [pageDrafts, setPageDrafts] = useState<PageDraft[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!projectId) return;
    async function load() {
      try {
        const [proj, drafts, leadList] = await Promise.all([
          getProject(projectId),
          getEntities<PageDraft>("page_draft", projectId),
          getEntities<Lead>("lead", projectId),
        ]);
        setProject(proj ?? null);
        setPageDrafts(drafts);
        setLeads(leadList);
      } catch {
        setProject(null);
        setPageDrafts([]);
        setLeads([]);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [projectId]);

  const publishedCount = pageDrafts.filter(
    (d) => (d.metadata?.status as string) === "published"
  ).length;
  const pendingDrafts = pageDrafts.length - publishedCount;

  const newLeads = leads.filter(
    (l) => (l.metadata?.status as string) === "new" || !l.metadata?.status
  ).length;
  const calledLeads = leads.filter(
    (l) => (l.metadata?.status as string) === "called"
  ).length;

  const displayName =
    project?.niche || projectId?.replace(/_/g, " ") || "Project";

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-64 animate-pulse rounded bg-muted" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <PulseCardSkeleton />
          <PulseCardSkeleton />
          <PulseCardSkeleton />
        </div>
        <div className="flex gap-3">
          <div className="h-10 w-36 animate-pulse rounded bg-muted" />
          <div className="h-10 w-32 animate-pulse rounded bg-muted" />
          <div className="h-10 w-28 animate-pulse rounded bg-muted" />
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

      {/* Pulse Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <PulseCard
          title="Traffic"
          primary={`${pageDrafts.length} drafts`}
          secondary={`${publishedCount} published · ${pendingDrafts} pending`}
        />
        <PulseCard
          title="Revenue"
          primary={`${leads.length} leads`}
          secondary={`${newLeads} new · ${calledLeads} called`}
        />
        <PulseCard
          title="System"
          primary="3 active"
          secondary="Scout · Strategist · Publisher"
        />
      </div>

      {/* Quick Actions */}
      <div className="space-y-3">
        <p className="text-sm font-medium text-muted-foreground">
          Quick Actions
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            href={`/projects/${projectId}/strategy`}
            className="acid-glow flex items-center gap-2 rounded border border-primary/50 bg-primary/10 px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
          >
            <Rocket className="h-4 w-4" />
            Launch Campaign
          </Link>
          <Link
            href={`/projects/${projectId}/leads`}
            className="flex items-center gap-2 rounded border border-border bg-muted/50 px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
          >
            <Users className="h-4 w-4" />
            View Leads
          </Link>
          <Link
            href={`/projects/${projectId}/settings`}
            className="flex items-center gap-2 rounded border border-border bg-muted/50 px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
          >
            <Dna className="h-4 w-4" />
            Edit DNA
          </Link>
        </div>
      </div>
    </div>
  );
}
