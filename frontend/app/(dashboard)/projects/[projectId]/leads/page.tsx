"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { getEntities, getCampaigns, connectCall, runNextForLead } from "@/lib/api";
import type { Lead } from "@/types";
import { Phone, X, Plus } from "lucide-react";
import { CreateCampaignDialog } from "@/components/campaigns/CreateCampaignDialog";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

function AiScoreBadge({ score }: { score: number | undefined }) {
  const s = score ?? 0;
  if (s > 80) {
    return (
      <span className="acid-glow acid-glow-green inline-flex items-center rounded px-2 py-0.5 text-xs font-medium text-neon-green">
        {s}
      </span>
    );
  }
  if (s < 40) {
    return (
      <span className="inline-flex items-center rounded bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
        {s}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded border border-border px-2 py-0.5 text-xs font-medium text-foreground">
      {s}
    </span>
  );
}

function StatusBadge({ status }: { status: string | undefined }) {
  const s = (status ?? "new").toLowerCase();
  if (s === "spam_blocked") {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-primary/30 px-2 py-0.5 text-xs font-medium text-primary">
        <X className="h-3 w-3" />
        Blocked
      </span>
    );
  }
  if (s === "called") {
    return (
      <span className="inline-flex items-center rounded bg-blue-500/20 px-2 py-0.5 text-xs font-medium text-blue-400">
        Called
      </span>
    );
  }
  if (s === "new") {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-secondary/20 px-2 py-0.5 text-xs font-medium text-secondary">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-secondary" />
        New
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
      {s}
    </span>
  );
}

function TableSkeleton() {
  return (
    <div className="glass-panel animate-pulse overflow-hidden">
      <div className="h-12 border-b border-border" />
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="flex h-14 border-b border-border last:border-0">
          <div className="w-1/5 bg-muted/50 p-3" />
          <div className="w-1/5 bg-muted/30 p-3" />
          <div className="w-1/4 bg-muted/30 p-3" />
          <div className="w-16 bg-muted/20 p-3" />
          <div className="w-24 bg-muted/20 p-3" />
          <div className="flex-1 bg-muted/20 p-3" />
        </div>
      ))}
    </div>
  );
}

export default function LeadsPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  const [leads, setLeads] = useState<Lead[]>([]);
  const [campaigns, setCampaigns] = useState<{ id: string; name: string; module: string; status: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [callingId, setCallingId] = useState<string | null>(null);
  const [runningLeadId, setRunningLeadId] = useState<string | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  /** Next step for phase-based row control: Score (no score yet) or Bridge (scheduled). */
  const getNextStepForLead = (lead: Lead): { label: string } | null => {
    const meta = (lead.metadata ?? {}) as Record<string, unknown>;
    if (meta.score === undefined || meta.score === null) return { label: "Score" };
    if (meta.bridge_status === "scheduled") return { label: "Bridge" };
    return null;
  };

  const loadLeads = useCallback(async () => {
    const data = await getEntities<Lead>("lead", projectId);
    setLeads(data);
  }, [projectId]);

  const loadCampaigns = useCallback(async () => {
    const data = await getCampaigns(projectId, "lead_gen");
    setCampaigns(data);
  }, [projectId]);

  useEffect(() => {
    async function load() {
      try {
        await Promise.all([loadLeads(), loadCampaigns()]);
      } catch {
        setLeads([]);
        setCampaigns([]);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [loadLeads, loadCampaigns]);

  const handleRunNextForLead = async (lead: Lead) => {
    const campaignId = (lead.metadata as Record<string, unknown> | undefined)?.campaign_id as string | undefined;
    const cid = campaignId ?? campaigns[0]?.id;
    if (!cid) {
      toast.error("No lead gen campaign for this lead.");
      return;
    }
    setRunningLeadId(lead.id);
    try {
      const res = await runNextForLead(projectId, cid, lead.id);
      if (res.status === "success") {
        toast.success(res.message ?? "Step completed");
      } else {
        toast.error(res.message ?? "Step failed");
      }
      await loadLeads();
    } catch {
      toast.error("Request failed");
      await loadLeads();
    } finally {
      setRunningLeadId(null);
    }
  };

  const handleCallNow = async (lead: Lead) => {
    const phone = lead.primary_contact ?? lead.metadata?.phone;
    if (!phone) {
      toast.error("No phone number for this lead.");
      return;
    }
    setCallingId(lead.id);
    const toastId = toast.loading("Connecting...", {
      style: {
        background: "hsl(240 3.7% 11.9%)",
        borderColor: "hsl(0 100% 60%)",
      },
    });
    try {
      const result = await connectCall(lead.id, projectId);
      toast.dismiss(toastId);
      if (result.status === "success") {
        toast.success("Call initiated. You will be connected shortly.");
        await loadLeads();
      } else {
        toast.error(result.message ?? "Call failed.");
      }
    } catch {
      toast.dismiss(toastId);
      toast.error("Call failed. Please try again.", {
        style: {
          background: "hsl(0 100% 60% / 0.2)",
          borderColor: "hsl(0 100% 60%)",
        },
      });
    } finally {
      setCallingId(null);
    }
  };

  const getServiceRequested = (lead: Lead) => {
    const data = lead.metadata?.data as Record<string, unknown> | undefined;
    const desc = lead.metadata?.description as string | undefined;
    if (data?.service) return String(data.service);
    if (data?.message) return String(data.message);
    if (desc) return desc;
    return "—";
  };

  return (
    <div className="space-y-6">
      <h1 className="acid-text text-2xl font-bold text-foreground">
        Lead Gen
      </h1>

      <section className="glass-panel rounded-lg border border-border p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">Campaigns</h2>
          <button
            type="button"
            onClick={() => setCreateDialogOpen(true)}
            className="acid-glow flex items-center gap-2 rounded bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            Create Campaign
          </button>
        </div>
        {campaigns.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">
            No Lead Gen campaigns yet. Create one to capture leads.
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {campaigns.map((c) => (
              <li
                key={c.id}
                className="flex items-center justify-between rounded border border-border bg-muted/30 px-3 py-2 text-sm"
              >
                <span className="font-medium text-foreground">{c.name}</span>
                <span className="text-xs text-muted-foreground">{c.status}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <h2 className="text-lg font-semibold text-foreground">Leads</h2>
      {loading ? (
        <TableSkeleton />
      ) : (
        <div className="glass-panel overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    Phone
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    Service Requested
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    AI Score
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    Status
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {leads.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-muted-foreground">
                      No leads yet.
                    </td>
                  </tr>
                ) : (
                  leads.map((lead) => (
                    <tr
                      key={lead.id}
                      className="border-b border-border last:border-0 transition-colors hover:bg-muted/30"
                    >
                      <td className="px-4 py-3 font-medium text-foreground">
                        {lead.name}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {lead.primary_contact ?? lead.metadata?.phone ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground max-w-[200px] truncate">
                        {getServiceRequested(lead)}
                      </td>
                      <td className="px-4 py-3">
                        <AiScoreBadge score={lead.metadata?.score as number} />
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge
                          status={lead.metadata?.status as string}
                        />
                      </td>
                      <td className="px-4 py-3 text-right">
                        {getNextStepForLead(lead) && (
                          <button
                            type="button"
                            onClick={() => handleRunNextForLead(lead)}
                            disabled={!!runningLeadId}
                            className={cn(
                              "mr-2 rounded border border-primary bg-primary/10 px-2 py-1 text-xs font-medium text-primary hover:bg-primary/20 disabled:opacity-50"
                            )}
                          >
                            {runningLeadId === lead.id ? "Running…" : `Run next (${getNextStepForLead(lead)?.label})`}
                          </button>
                        )}
                        {(lead.metadata?.status as string) !== "spam_blocked" &&
                          (lead.primary_contact ?? lead.metadata?.phone) && (
                            <button
                              type="button"
                              onClick={() => handleCallNow(lead)}
                              disabled={!!callingId}
                              className={cn(
                                "acid-glow inline-flex items-center gap-2 rounded bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                              )}
                            >
                              <Phone className="h-4 w-4" />
                              {callingId === lead.id ? "Connecting..." : "Call Now"}
                            </button>
                          )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <CreateCampaignDialog
        isOpen={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        onSuccess={() => {
          setCreateDialogOpen(false);
          loadCampaigns();
        }}
        projectId={projectId}
        module="lead_gen"
      />
    </div>
  );
}
