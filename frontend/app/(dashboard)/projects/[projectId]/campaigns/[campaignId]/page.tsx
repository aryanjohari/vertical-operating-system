"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getCampaign,
  getCampaigns,
  getCampaignDrafts,
  getPseoStats,
  runPseoStep,
  runNextForDraft,
  updateCampaignConfig,
  updateEntity,
  deleteEntity,
  getFormSchema,
} from "@/lib/api";
import { toast } from "sonner";
import { DynamicForm } from "@/components/forms/DynamicForm";
import type { FormSchema } from "@/lib/api";

const PAGE_SIZE = 20;

const PHASES: { key: string; label: string; step: string; statKey: string }[] = [
  { key: "scout", label: "Scout", step: "scout_anchors", statKey: "anchors" },
  { key: "strategist", label: "Strategist", step: "strategist_run", statKey: "drafts_total" },
  { key: "writer", label: "Writer", step: "write_pages", statKey: "drafts_pending_writer" },
  { key: "critic", label: "Critic", step: "critic_review", statKey: "1_unreviewed" },
  { key: "librarian", label: "Librarian", step: "librarian_link", statKey: "2_validated" },
  { key: "media", label: "Media", step: "enhance_media", statKey: "3_linked" },
  { key: "utility", label: "Utility", step: "enhance_utility", statKey: "4_imaged" },
  { key: "publisher", label: "Publisher", step: "publish", statKey: "5_ready" },
];

/** Draft statuses that have a "Run next" step (phase-based row control). */
const DRAFT_STATUS_WITH_NEXT_STEP = new Set([
  "pending_writer",
  "draft",
  "rejected",
  "validated",
  "ready_for_media",
  "ready_for_utility",
  "utility_validation_failed",
  "ready_to_publish",
]);

function getNextStepLabel(status: string): string {
  const map: Record<string, string> = {
    pending_writer: "Write",
    draft: "Review",
    rejected: "Review",
    validated: "Link",
    ready_for_media: "Add image",
    ready_for_utility: "Utility",
    utility_validation_failed: "Utility",
    ready_to_publish: "Publish",
  };
  return map[status] ?? "—";
}

type Campaign = {
  id: string;
  name: string;
  module: string;
  status: string;
  config?: Record<string, unknown>;
};

type Stats = Record<string, unknown> & {
  anchors?: number;
  drafts_total?: number;
  drafts_pending_writer?: number;
  "1_unreviewed"?: number;
  "2_validated"?: number;
  "3_linked"?: number;
  "4_imaged"?: number;
  "5_ready"?: number;
  "6_live"?: number;
};

type NextStep = {
  agent_key: string | null;
  label: string;
  description: string;
  reason: string;
};

export default function CampaignDashboardPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const campaignId = params.campaignId as string;

  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [nextStep, setNextStep] = useState<NextStep | null>(null);
  const [drafts, setDrafts] = useState<{ entities: Array<Record<string, unknown>>; total: number }>({
    entities: [],
    total: 0,
  });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState<string | null>(null);
  const [runningDraftId, setRunningDraftId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editH1, setEditH1] = useState("");
  const [editKeywords, setEditKeywords] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsSchema, setSettingsSchema] = useState<FormSchema | null>(null);
  const [settingsDefaults, setSettingsDefaults] = useState<Record<string, unknown>>({});

  const loadCampaign = useCallback(async () => {
    if (!projectId || !campaignId) return;
    const list = await getCampaigns(projectId);
    const c = list.find((x) => x.id === campaignId) ?? null;
    setCampaign(c ? { ...c, config: c.config } : null);
  }, [projectId, campaignId]);

  const loadStats = useCallback(async () => {
    if (!projectId || !campaignId) return;
    const { stats: s, next_step: ns } = await getPseoStats(projectId, campaignId);
    setStats(s as Stats);
    setNextStep(ns);
  }, [projectId, campaignId]);

  const loadDrafts = useCallback(async () => {
    if (!projectId || !campaignId) return;
    const res = await getCampaignDrafts(projectId, campaignId, page, PAGE_SIZE);
    setDrafts(res);
  }, [projectId, campaignId, page]);

  const refresh = useCallback(() => {
    loadCampaign();
    loadStats();
    loadDrafts();
  }, [loadCampaign, loadStats, loadDrafts]);

  useEffect(() => {
    if (!projectId || !campaignId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        await Promise.all([loadCampaign(), loadStats(), loadDrafts()]);
      } catch (e) {
        if (!cancelled) toast.error("Failed to load campaign data");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, campaignId, loadCampaign, loadStats, loadDrafts]);

  const handleRunStep = useCallback(
    async (step: string) => {
      if (!projectId || !campaignId || running) return;
      setRunning(step);
      try {
        const res = await runPseoStep(projectId, campaignId, step);
        if (res.status === "error" || res.status === "partial") {
          toast.error(res.message || "Step failed");
        } else {
          toast.success(res.message || "Step completed");
        }
        await loadStats();
        await loadDrafts();
      } catch (e) {
        toast.error("Request failed");
      } finally {
        setRunning(null);
      }
    },
    [projectId, campaignId, running, loadStats, loadDrafts]
  );

  const openSettings = useCallback(async () => {
    if (!projectId || !campaignId) return;
    setSettingsOpen(true);
    try {
      const fullCampaign = await getCampaign(projectId, campaignId);
      const schemaType = fullCampaign.module === "lead_gen" ? "lead_gen" : "pseo";
      const schemaRes = await getFormSchema(schemaType);
      setSettingsSchema(schemaRes.schema);
      setSettingsDefaults((fullCampaign.config ?? schemaRes.defaults ?? {}) as Record<string, unknown>);
      setCampaign((c) => (c ? { ...c, config: fullCampaign.config } : null));
    } catch (e) {
      toast.error("Failed to load settings");
    }
  }, [projectId, campaignId]);

  const handleSaveSettings = useCallback(
    async (values: Record<string, unknown>) => {
      if (!projectId || !campaignId) return;
      try {
        await updateCampaignConfig(projectId, campaignId, values);
        toast.success("Campaign settings saved.");
        setSettingsOpen(false);
        await loadCampaign();
      } catch {
        toast.error("Failed to save settings.");
      }
    },
    [projectId, campaignId, loadCampaign]
  );

  const getPrimaryAction = () => {
    const anchors = (stats?.anchors as number) ?? 0;
    const total = (stats?.drafts_total as number) ?? 0;
    if (anchors === 0) return { label: "Start Scout Agent", step: "scout_anchors" };
    if (total === 0) return { label: "Run Strategist", step: "strategist_run" };
    return { label: "Run Writer", step: "write_pages" };
  };

  const handleDelete = useCallback(
    async (draftId: string) => {
      if (!confirm("Delete this draft?")) return;
      try {
        await deleteEntity(draftId);
        toast.success("Draft deleted");
        refresh();
      } catch {
        toast.error("Failed to delete");
      }
    },
    [refresh]
  );

  const startEdit = (d: Record<string, unknown>) => {
    const meta = (d.metadata as Record<string, unknown>) || {};
    setEditingId(d.id as string);
    setEditH1((meta.h1_title as string) ?? "");
    setEditKeywords((Array.isArray(meta.secondary_keywords) ? (meta.secondary_keywords as string[]).join(", ") : "") ?? "");
  };

  const saveEdit = useCallback(
    async () => {
      if (!editingId) return;
      try {
        const d = drafts.entities.find((x) => x.id === editingId);
        if (!d) return;
        const existing = (d.metadata as Record<string, unknown>) || {};
        const meta = {
          ...existing,
          h1_title: editH1,
          secondary_keywords: editKeywords.split(",").map((s) => s.trim()).filter(Boolean),
        };
        await updateEntity(editingId, meta);
        toast.success("Draft updated");
        setEditingId(null);
        refresh();
      } catch {
        toast.error("Failed to update");
      }
    },
    [editingId, editH1, editKeywords, drafts.entities, refresh]
  );

  const handleRunNextForDraft = useCallback(
    async (draftId: string) => {
      if (!projectId || !campaignId) return;
      setRunningDraftId(draftId);
      try {
        const res = await runNextForDraft(projectId, campaignId, draftId);
        if (res.status === "success" || res.status === "complete") {
          toast.success(res.message ?? "Step completed");
        } else {
          toast.error(res.message ?? "Step failed");
        }
        refresh();
      } catch {
        toast.error("Request failed");
        refresh();
      } finally {
        setRunningDraftId(null);
      }
    },
    [projectId, campaignId, refresh]
  );

  const pipelineStatus =
    nextStep?.reason ||
    (stats?.anchors === 0 ? "Ready to Scout" : (stats?.drafts_total as number) > 0 ? "Drafts ready" : "Ready to Write");

  if (loading && !campaign) {
    return (
      <div className="space-y-4 p-4">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="h-64 animate-pulse rounded-lg bg-muted" />
      </div>
    );
  }

  if (!campaign) {
    return (
      <div className="glass-panel p-8 text-center">
        <p className="text-muted-foreground">Campaign not found.</p>
        <Link href={`/projects/${projectId}`} className="mt-4 inline-block text-primary hover:underline">
          Back to project
        </Link>
      </div>
    );
  }

  const primary = getPrimaryAction();
  const totalPages = Math.max(1, Math.ceil(drafts.total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link href={`/projects/${projectId}`} className="text-muted-foreground hover:text-foreground">
            ← Project
          </Link>
          <h1 className="acid-text text-2xl font-bold text-foreground">{campaign.name}</h1>
        </div>
        <button
          type="button"
          onClick={openSettings}
          className="rounded border border-border bg-muted/50 px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
        >
          Campaign settings
        </button>
      </div>

      {/* Phase-based pipeline (pSEO only) */}
      {campaign.module === "pseo" && (
        <>
          <section className="glass-panel rounded-lg border border-border p-4">
            <h2 className="mb-4 text-lg font-semibold text-foreground">Pipeline phases</h2>
            <p className="mb-4 text-sm text-muted-foreground">{pipelineStatus}</p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
              {PHASES.map(({ key, label, step, statKey }) => {
                const count = (stats?.[statKey as keyof Stats] as number) ?? 0;
                const isRunning = running === step;
                const librarianWaiting =
                  step === "librarian_link" && (stats?.["1_unreviewed"] as number) > 0;
                return (
                  <div
                    key={key}
                    className="rounded-lg border border-border bg-muted/30 p-3"
                  >
                    <p className="text-xs font-medium text-muted-foreground">{label}</p>
                    <p className="mt-1 text-lg font-semibold text-foreground">{count}</p>
                    <button
                      type="button"
                      onClick={() => handleRunStep(step)}
                      disabled={!!running || librarianWaiting}
                      title={librarianWaiting ? "Complete Critic for all pages first" : undefined}
                      className="mt-2 w-full rounded bg-primary px-2 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
                    >
                      {isRunning ? "Running…" : "Run"}
                    </button>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="glass-panel rounded-lg border border-border p-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <p className="text-sm text-muted-foreground">Recommended next step</p>
              <button
                type="button"
                onClick={() => handleRunStep(primary.step)}
                disabled={!!running}
                className="acid-glow rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-60"
              >
                {running ? "Running…" : primary.label}
              </button>
            </div>
          </section>
        </>
      )}

      {/* Data grid: Page drafts (pSEO shows drafts; lead_gen can use same table if needed) */}
      <section className="glass-panel rounded-lg border border-border p-4">
        <h2 className="mb-4 text-lg font-semibold text-foreground">Page drafts</h2>
        {drafts.entities.length === 0 ? (
          <p className="text-sm text-muted-foreground">No drafts yet. Run Strategist to create drafts.</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="p-2 text-left font-medium text-foreground">Target anchor</th>
                    <th className="p-2 text-left font-medium text-foreground">Intent cluster</th>
                    <th className="p-2 text-left font-medium text-foreground">H1 title</th>
                    <th className="p-2 text-left font-medium text-foreground">Score</th>
                    <th className="p-2 text-left font-medium text-foreground">Status</th>
                    <th className="p-2 text-right font-medium text-foreground">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {drafts.entities.map((d) => {
                    const meta = (d.metadata as Record<string, unknown>) || {};
                    const status = (meta.status as string) || "—";
                    const score = (meta.qa_score as number) ?? (meta.validation_score as number) ?? 0;
                    const scoreColor =
                      score >= 7
                        ? "bg-green-500/20 text-green-700 dark:text-green-400"
                        : score > 0
                          ? "bg-yellow-500/20 text-yellow-700 dark:text-yellow-400"
                          : "bg-muted text-muted-foreground";
                    const isEditing = editingId === d.id;
                    return (
                      <tr key={d.id as string} className="border-b border-border/50">
                        <td className="p-2 text-foreground">{(meta.anchor_name as string) ?? "—"}</td>
                        <td className="p-2 text-foreground">{(meta.cluster_id as string) ?? "—"}</td>
                        <td className="p-2">
                          {isEditing ? (
                            <input
                              value={editH1}
                              onChange={(e) => setEditH1(e.target.value)}
                              className="w-full rounded border border-border bg-background px-2 py-1 text-foreground"
                            />
                          ) : (
                            <span className="text-foreground">{(meta.h1_title as string) ?? (d.name as string) ?? "—"}</span>
                          )}
                        </td>
                        <td className="p-2">
                          <span className={`inline-block rounded px-2 py-0.5 text-xs ${scoreColor}`}>
                            {score}
                          </span>
                        </td>
                        <td className="p-2 text-foreground">{status}</td>
                        <td className="p-2 text-right">
                          {isEditing ? (
                            <>
                              <button
                                type="button"
                                onClick={saveEdit}
                                className="mr-2 text-primary hover:underline"
                              >
                                Save
                              </button>
                              <button
                                type="button"
                                onClick={() => setEditingId(null)}
                                className="text-muted-foreground hover:underline"
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <>
                              {DRAFT_STATUS_WITH_NEXT_STEP.has(status) && (
                                <button
                                  type="button"
                                  onClick={() => handleRunNextForDraft(d.id as string)}
                                  disabled={runningDraftId === d.id}
                                  className="mr-2 rounded border border-primary bg-primary/10 px-2 py-1 text-xs font-medium text-primary hover:bg-primary/20 disabled:opacity-50"
                                >
                                  {runningDraftId === d.id ? "Running…" : `Run next (${getNextStepLabel(status)})`}
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={() => startEdit(d)}
                                className="mr-2 text-primary hover:underline"
                              >
                                Edit
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDelete(d.id as string)}
                                className="mr-2 text-destructive hover:underline"
                              >
                                Delete
                              </button>
                              {meta.content && (
                                <button
                                  type="button"
                                  onClick={() => window.open("#preview-" + d.id, "_blank")}
                                  className="text-muted-foreground hover:underline"
                                >
                                  Preview
                                </button>
                              )}
                            </>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  Page {page} of {totalPages} ({drafts.total} total)
                </p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    className="rounded border border-border px-3 py-1 text-sm disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                    className="rounded border border-border px-3 py-1 text-sm disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </section>

      {/* Settings drawer */}
      {settingsOpen && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div
            className="absolute inset-0 bg-background/80 backdrop-blur-sm"
            onClick={() => setSettingsOpen(false)}
            aria-hidden
          />
          <div className="relative z-10 w-full max-w-xl overflow-y-auto border-l border-border bg-background p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">Campaign settings</h2>
              <button
                type="button"
                onClick={() => setSettingsOpen(false)}
                className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                ×
              </button>
            </div>
            {settingsSchema ? (
              <DynamicForm
                schema={settingsSchema}
                defaults={settingsDefaults}
                onSubmit={handleSaveSettings}
                submitLabel="Save settings"
                onCancel={() => setSettingsOpen(false)}
              />
            ) : (
              <p className="text-sm text-muted-foreground">Loading form…</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
