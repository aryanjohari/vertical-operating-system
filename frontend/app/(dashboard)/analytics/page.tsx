"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  getProjects,
  getCampaigns,
  getAnalyticsSnapshot,
  refetchAnalytics,
} from "@/lib/api";
import type { Project } from "@/types";
import type { LeadGenAnalytics, PseoAnalytics } from "@/types";
import { Zap, FileText, RefreshCw, AlertCircle, CheckCircle, Globe } from "lucide-react";

type Campaign = { id: string; name: string; module: string; status: string };
type Scope = "project" | "campaign";

function last30Days(): { from: string; to: string } {
  const to = new Date();
  const from = new Date(to);
  from.setDate(from.getDate() - 30);
  return {
    from: from.toISOString().slice(0, 10),
    to: to.toISOString().slice(0, 10),
  };
}

const POLL_AFTER_REFETCH_MS = 2500;
const POLL_INTERVAL_MS = 2000;
const POLL_MAX_ATTEMPTS = 30;
const SUCCESS_MESSAGE_DURATION_MS = 4000;
const PROJECT_CAMPAIGN_ID = "";

export default function AnalyticsDashboardPage() {
  const [scope, setScope] = useState<Scope>("project");
  const [projects, setProjects] = useState<Project[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(null);
  const [dateRange] = useState(last30Days());
  const [leadGenData, setLeadGenData] = useState<LeadGenAnalytics | null>(null);
  const [pseoData, setPseoData] = useState<PseoAnalytics | null>(null);
  const [wholeSiteData, setWholeSiteData] = useState<PseoAnalytics | null>(null);
  const [fetchedAtLeadGen, setFetchedAtLeadGen] = useState<string | null>(null);
  const [fetchedAtPseo, setFetchedAtPseo] = useState<string | null>(null);
  const [fetchedAtWholeSite, setFetchedAtWholeSite] = useState<string | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [refetching, setRefetching] = useState(false);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  const [refetchError, setRefetchError] = useState<string | null>(null);
  const [refetchSuccess, setRefetchSuccess] = useState(false);

  const loadProjects = useCallback(async () => {
    try {
      const data = await getProjects();
      setProjects(data);
      if (data.length && !selectedProjectId) setSelectedProjectId(data[0].project_id);
    } catch {
      setProjects([]);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const loadCampaigns = useCallback(async () => {
    if (!selectedProjectId) {
      setCampaigns([]);
      return;
    }
    try {
      const list = await getCampaigns(selectedProjectId);
      setCampaigns(list);
      setSelectedCampaignId(list.length ? list[0].id : null);
    } catch {
      setCampaigns([]);
      setSelectedCampaignId(null);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    loadCampaigns();
  }, [loadCampaigns]);

  const selectedCampaign = campaigns.find((c) => c.id === selectedCampaignId);

  const loadSnapshotProject = useCallback(async () => {
    if (!selectedProjectId) return;
    setSnapshotLoading(true);
    setSnapshotError(null);
    const { from, to } = dateRange;
    try {
      const [lgRes, pseoRes, wholeRes] = await Promise.all([
        getAnalyticsSnapshot(selectedProjectId, {
          campaignId: PROJECT_CAMPAIGN_ID,
          from,
          to,
          module: "lead_gen",
        }),
        getAnalyticsSnapshot(selectedProjectId, {
          campaignId: PROJECT_CAMPAIGN_ID,
          from,
          to,
          module: "pseo",
        }),
        getAnalyticsSnapshot(selectedProjectId, {
          campaignId: PROJECT_CAMPAIGN_ID,
          from,
          to,
          module: "pseo_whole_site",
        }),
      ]);
      setFetchedAtLeadGen(lgRes.fetched_at ?? null);
      setFetchedAtPseo(pseoRes.fetched_at ?? null);
      setFetchedAtWholeSite(wholeRes.fetched_at ?? null);
      setLeadGenData((lgRes.payload as LeadGenAnalytics) ?? null);
      setPseoData((pseoRes.payload as PseoAnalytics) ?? null);
      setWholeSiteData((wholeRes.payload as PseoAnalytics) ?? null);
    } catch (e) {
      setLeadGenData(null);
      setPseoData(null);
      setWholeSiteData(null);
      setFetchedAtLeadGen(null);
      setFetchedAtPseo(null);
      setFetchedAtWholeSite(null);
      setSnapshotError(e instanceof Error ? e.message : "Failed to load analytics");
    } finally {
      setSnapshotLoading(false);
    }
  }, [selectedProjectId, dateRange]);

  const loadSnapshotCampaign = useCallback(async () => {
    if (!selectedProjectId || !selectedCampaign) return;
    setSnapshotLoading(true);
    setSnapshotError(null);
    const { from, to } = dateRange;
    try {
      const res = await getAnalyticsSnapshot(selectedProjectId, {
        campaignId: selectedCampaign.id,
        from,
        to,
        module: selectedCampaign.module as "lead_gen" | "pseo",
      });
      const at = res.fetched_at ?? null;
      setFetchedAtLeadGen(at);
      setFetchedAtPseo(at);
      if (selectedCampaign.module === "lead_gen") {
        setPseoData(null);
        setLeadGenData((res.payload as LeadGenAnalytics) ?? null);
      } else {
        setLeadGenData(null);
        setPseoData((res.payload as PseoAnalytics) ?? null);
      }
    } catch (e) {
      setLeadGenData(null);
      setPseoData(null);
      setFetchedAtLeadGen(null);
      setFetchedAtPseo(null);
      setSnapshotError(e instanceof Error ? e.message : "Failed to load analytics");
    } finally {
      setSnapshotLoading(false);
    }
  }, [selectedProjectId, selectedCampaignId, selectedCampaign?.id, selectedCampaign?.module, dateRange]);

  useEffect(() => {
    if (scope === "project") {
      if (!selectedProjectId) {
        setLeadGenData(null);
        setPseoData(null);
        setWholeSiteData(null);
        setFetchedAtLeadGen(null);
        setFetchedAtPseo(null);
        setFetchedAtWholeSite(null);
        setSnapshotError(null);
        return;
      }
      loadSnapshotProject();
    } else {
      if (!selectedProjectId || !selectedCampaign) {
        setLeadGenData(null);
        setPseoData(null);
        setWholeSiteData(null);
        setFetchedAtLeadGen(null);
        setFetchedAtPseo(null);
        setFetchedAtWholeSite(null);
        setSnapshotError(null);
        return;
      }
      loadSnapshotCampaign();
    }
  }, [scope, selectedProjectId, selectedCampaignId, selectedCampaign?.id, loadSnapshotProject, loadSnapshotCampaign]);

  const handleRefetchProject = useCallback(async () => {
    if (!selectedProjectId) return;
    setRefetching(true);
    setRefetchError(null);
    setRefetchSuccess(false);
    const { from, to } = dateRange;
    try {
      await Promise.all([
        refetchAnalytics(selectedProjectId, {
          campaign_id: PROJECT_CAMPAIGN_ID,
          from,
          to,
          module: "lead_gen",
        }),
        refetchAnalytics(selectedProjectId, {
          campaign_id: PROJECT_CAMPAIGN_ID,
          from,
          to,
          module: "pseo",
        }),
        refetchAnalytics(selectedProjectId, {
          campaign_id: PROJECT_CAMPAIGN_ID,
          from,
          to,
          module: "pseo_whole_site",
        }),
      ]);
      const prevLg = fetchedAtLeadGen;
      const prevPseo = fetchedAtPseo;
      const prevWhole = fetchedAtWholeSite;
      const deadline = Date.now() + POLL_AFTER_REFETCH_MS + POLL_MAX_ATTEMPTS * POLL_INTERVAL_MS;
      const check = () => {
        if (Date.now() > deadline) {
          setRefetching(false);
          setRefetchError("Refetch timed out. Data may still update shortly.");
          loadSnapshotProject();
          return;
        }
        Promise.all([
          getAnalyticsSnapshot(selectedProjectId, {
            campaignId: PROJECT_CAMPAIGN_ID,
            from,
            to,
            module: "lead_gen",
          }),
          getAnalyticsSnapshot(selectedProjectId, {
            campaignId: PROJECT_CAMPAIGN_ID,
            from,
            to,
            module: "pseo",
          }),
          getAnalyticsSnapshot(selectedProjectId, {
            campaignId: PROJECT_CAMPAIGN_ID,
            from,
            to,
            module: "pseo_whole_site",
          }),
        ])
          .then(([lgRes, pseoRes, wholeRes]) => {
            const lgUpdated = lgRes.fetched_at && lgRes.fetched_at !== prevLg;
            const pseoUpdated = pseoRes.fetched_at && pseoRes.fetched_at !== prevPseo;
            const wholeUpdated = wholeRes.fetched_at && wholeRes.fetched_at !== prevWhole;
            if (lgUpdated || pseoUpdated || wholeUpdated) {
              setFetchedAtLeadGen(lgRes.fetched_at ?? null);
              setFetchedAtPseo(pseoRes.fetched_at ?? null);
              setFetchedAtWholeSite(wholeRes.fetched_at ?? null);
              setLeadGenData((lgRes.payload as LeadGenAnalytics) ?? null);
              setPseoData((pseoRes.payload as PseoAnalytics) ?? null);
              setWholeSiteData((wholeRes.payload as PseoAnalytics) ?? null);
              setRefetching(false);
              setRefetchSuccess(true);
              setTimeout(() => setRefetchSuccess(false), SUCCESS_MESSAGE_DURATION_MS);
              return;
            }
            setTimeout(check, POLL_INTERVAL_MS);
          })
          .catch((e) => {
            setRefetching(false);
            setRefetchError(e instanceof Error ? e.message : "Refetch failed");
            loadSnapshotProject();
          });
      };
      setTimeout(check, POLL_AFTER_REFETCH_MS);
    } catch (e) {
      setRefetching(false);
      setRefetchError(e instanceof Error ? e.message : "Refetch failed");
      loadSnapshotProject();
    }
  }, [selectedProjectId, dateRange, fetchedAtLeadGen, fetchedAtPseo, fetchedAtWholeSite, loadSnapshotProject]);

  const handleRefetchCampaign = useCallback(async () => {
    if (!selectedProjectId || !selectedCampaign) return;
    setRefetching(true);
    setRefetchError(null);
    setRefetchSuccess(false);
    const { from, to } = dateRange;
    const previousFetchedAt = fetchedAtLeadGen || fetchedAtPseo;
    try {
      await refetchAnalytics(selectedProjectId, {
        campaign_id: selectedCampaign.id,
        from,
        to,
        module: selectedCampaign.module as "lead_gen" | "pseo",
      });
      const deadline = Date.now() + POLL_AFTER_REFETCH_MS + POLL_MAX_ATTEMPTS * POLL_INTERVAL_MS;
      const check = () => {
        if (Date.now() > deadline) {
          setRefetching(false);
          setRefetchError("Refetch timed out. Data may still update shortly.");
          loadSnapshotCampaign();
          return;
        }
        getAnalyticsSnapshot(selectedProjectId, {
          campaignId: selectedCampaign.id,
          from,
          to,
          module: selectedCampaign.module as "lead_gen" | "pseo",
        }).then((res) => {
          if (res.fetched_at && res.fetched_at !== previousFetchedAt) {
            const at = res.fetched_at;
            setFetchedAtLeadGen(at);
            setFetchedAtPseo(at);
            if (selectedCampaign.module === "lead_gen") {
              setLeadGenData((res.payload as LeadGenAnalytics) ?? null);
              setPseoData(null);
            } else {
              setLeadGenData(null);
              setPseoData((res.payload as PseoAnalytics) ?? null);
            }
            setRefetching(false);
            setRefetchSuccess(true);
            setTimeout(() => setRefetchSuccess(false), SUCCESS_MESSAGE_DURATION_MS);
            return;
          }
          setTimeout(check, POLL_INTERVAL_MS);
        }).catch((e) => {
          setRefetching(false);
          setRefetchError(e instanceof Error ? e.message : "Refetch failed");
          loadSnapshotCampaign();
        });
      };
      setTimeout(check, POLL_AFTER_REFETCH_MS);
    } catch (e) {
      setRefetching(false);
      setRefetchError(e instanceof Error ? e.message : "Refetch failed");
      loadSnapshotCampaign();
    }
  }, [selectedProjectId, selectedCampaign, dateRange, fetchedAtLeadGen, fetchedAtPseo, loadSnapshotCampaign]);

  const handleRefetch = scope === "project" ? handleRefetchProject : handleRefetchCampaign;
  const canRefetch =
    scope === "project"
      ? !!selectedProjectId
      : !!selectedProjectId && !!selectedCampaign;
  const showContent =
    scope === "project"
      ? !!selectedProjectId
      : !!selectedProjectId && !!selectedCampaign;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="acid-text text-2xl font-bold text-foreground">
          Analytics
        </h1>
        <Link
          href="/projects"
          className="text-sm text-primary hover:underline"
        >
          View all projects
        </Link>
      </div>

      {(snapshotError || refetchError || refetchSuccess) && (
        <div className="flex flex-col gap-2">
          {snapshotError && (
            <div className="flex items-center gap-2 rounded-lg border border-red-500/50 bg-red-500/10 px-4 py-3 text-sm text-red-600 dark:text-red-400">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>Failed to load analytics: {snapshotError}</span>
            </div>
          )}
          {refetchError && (
            <div className="flex items-center gap-2 rounded-lg border border-red-500/50 bg-red-500/10 px-4 py-3 text-sm text-red-600 dark:text-red-400">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{refetchError}</span>
            </div>
          )}
          {refetchSuccess && (
            <div className="flex items-center gap-2 rounded-lg border border-green-500/50 bg-green-500/10 px-4 py-3 text-sm text-green-600 dark:text-green-400">
              <CheckCircle className="h-4 w-4 shrink-0" />
              <span>Data updated successfully.</span>
            </div>
          )}
        </div>
      )}

      <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <span className="text-xs font-medium text-muted-foreground">Scope</span>
          <div className="flex rounded-lg border border-border bg-muted/30 p-0.5">
            <button
              type="button"
              onClick={() => setScope("project")}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                scope === "project"
                  ? "bg-primary text-primary-foreground"
                  : "text-foreground hover:bg-muted"
              }`}
            >
              Whole project
            </button>
            <button
              type="button"
              onClick={() => setScope("campaign")}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                scope === "campaign"
                  ? "bg-primary text-primary-foreground"
                  : "text-foreground hover:bg-muted"
              }`}
            >
              By campaign
            </button>
          </div>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">
            Project
          </label>
          <select
            value={selectedProjectId ?? ""}
            onChange={(e) => setSelectedProjectId(e.target.value || null)}
            className="w-full min-w-0 rounded border border-border bg-muted/50 px-3 py-2 text-sm text-foreground sm:w-auto"
          >
            <option value="">Select project</option>
            {projects.map((p) => (
              <option key={p.project_id} value={p.project_id}>
                {p.niche || p.project_id}
              </option>
            ))}
          </select>
        </div>
        {scope === "campaign" && (
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Campaign
            </label>
            <select
              value={selectedCampaignId ?? ""}
              onChange={(e) => setSelectedCampaignId(e.target.value || null)}
              className="w-full min-w-0 rounded border border-border bg-muted/50 px-3 py-2 text-sm text-foreground sm:w-auto"
            >
              <option value="">Select campaign</option>
              {campaigns.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.module})
                </option>
              ))}
            </select>
          </div>
        )}
        {canRefetch && (
          <button
            type="button"
            onClick={handleRefetch}
            disabled={refetching}
            className="acid-glow flex w-full items-center justify-center gap-2 rounded bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-60 sm:w-auto"
          >
            <RefreshCw className={`h-4 w-4 ${refetching ? "animate-spin" : ""}`} />
            {refetching ? "Refreshing…" : "Refetch"}
          </button>
        )}
      </div>

      {!showContent ? (
        <div className="glass-panel flex min-h-[200px] items-center justify-center rounded-lg border border-border p-8">
          <p className="text-center text-muted-foreground">
            {scope === "project"
              ? "Select a project to see whole-project analytics (Lead Gen + pSEO)."
              : "Select a project and campaign to see campaign analytics."}
          </p>
        </div>
      ) : snapshotLoading && !leadGenData && !pseoData && !wholeSiteData ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="h-48 animate-pulse rounded-lg bg-muted" />
          <div className="h-48 animate-pulse rounded-lg bg-muted" />
          {scope === "project" && <div className="h-48 animate-pulse rounded-lg bg-muted" />}
        </div>
      ) : (
        <div className={`grid gap-6 ${scope === "project" ? "sm:grid-cols-2 lg:grid-cols-3" : "sm:grid-cols-2"}`}>
          <section className="glass-panel rounded-lg border border-border p-4 sm:p-6">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground">
              <Zap className="h-5 w-5 text-primary" />
              Money Machine
              {scope === "project" && (
                <span className="text-xs font-normal text-muted-foreground">
                  (all campaigns)
                </span>
              )}
            </h2>
            {scope === "project" || selectedCampaign?.module === "lead_gen" ? (
              leadGenData ? (
                <div className="space-y-4">
                  {fetchedAtLeadGen && (
                    <p className="text-xs text-muted-foreground">
                      Last updated: {new Date(fetchedAtLeadGen).toLocaleString()}
                    </p>
                  )}
                  <div className="text-sm text-muted-foreground">
                    {leadGenData.from} → {leadGenData.to}
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded bg-muted/50 p-3">
                      <div className="text-2xl font-bold text-foreground">
                        {leadGenData.webhooks_received}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Webhooks received
                      </div>
                    </div>
                    <div className="rounded bg-muted/50 p-3">
                      <div className="text-2xl font-bold text-foreground">
                        {leadGenData.avg_lead_score ?? "—"}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Avg lead score
                      </div>
                    </div>
                  </div>
                  <div className="rounded bg-muted/50 p-3">
                    <div className="text-sm font-medium text-foreground">
                      Scheduled bridge: {leadGenData.scheduled_bridge.count} / {leadGenData.scheduled_bridge.total} ({leadGenData.scheduled_bridge.pct}%)
                    </div>
                  </div>
                  {leadGenData.by_source && Object.keys(leadGenData.by_source).length > 0 && (
                    <div className="text-xs text-muted-foreground">
                      By source: {Object.entries(leadGenData.by_source).map(([k, v]) => `${k}: ${v}`).join(", ")}
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-muted-foreground">
                  No data yet. Click Refetch to load analytics.
                </p>
              )
            ) : (
              <p className="text-muted-foreground">
                Select a Lead Gen campaign for Money Machine stats.
              </p>
            )}
          </section>

          <section className="glass-panel rounded-lg border border-border p-4 sm:p-6">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground">
              <FileText className="h-5 w-5 text-primary" />
              pSEO Factory
              {scope === "project" && (
                <span className="text-xs font-normal text-muted-foreground">
                  (whole site)
                </span>
              )}
            </h2>
            {scope === "project" || selectedCampaign?.module === "pseo" ? (
              pseoData ? (
                <div className="space-y-4">
                  {fetchedAtPseo && (
                    <p className="text-xs text-muted-foreground">
                      Last updated: {new Date(fetchedAtPseo).toLocaleString()}
                    </p>
                  )}
                  {!pseoData.gsc_connected && (
                    <p className="text-sm text-amber-600 dark:text-amber-400">
                      Connect Google Search Console to see organic performance.
                    </p>
                  )}
                  <div className="text-sm text-muted-foreground">
                    {pseoData.from} → {pseoData.to}
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded bg-muted/50 p-3">
                      <div className="text-2xl font-bold text-foreground">
                        {pseoData.organic_clicks}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Organic clicks
                      </div>
                    </div>
                    <div className="rounded bg-muted/50 p-3">
                      <div className="text-2xl font-bold text-foreground">
                        {pseoData.organic_impressions}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Impressions
                      </div>
                    </div>
                  </div>
                  <div className="rounded bg-muted/50 p-3">
                    <div className="text-sm font-medium text-foreground">
                      CTR: {pseoData.ctr}% · {pseoData.filtered_pages_count} pages
                    </div>
                  </div>
                  {pseoData.per_page && pseoData.per_page.length > 0 && (
                    <div className="max-h-32 overflow-y-auto text-xs text-muted-foreground">
                      {pseoData.per_page.slice(0, 5).map((row, i) => (
                        <div key={i}>{row.url}: {row.clicks} clicks</div>
                      ))}
                      {pseoData.per_page.length > 5 && (
                        <div>… and {pseoData.per_page.length - 5} more</div>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-muted-foreground">
                  No data yet. Click Refetch to load analytics.
                </p>
              )
            ) : (
              <p className="text-muted-foreground">
                Select a pSEO campaign for pSEO Factory stats.
              </p>
            )}
          </section>

          {scope === "project" && (
            <section className="glass-panel rounded-lg border border-border p-4 sm:p-6">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground">
                <Globe className="h-5 w-5 text-primary" />
                Site overall (GSC)
                <span className="text-xs font-normal text-muted-foreground">
                  (all pages in Search Console)
                </span>
              </h2>
              {wholeSiteData ? (
                <div className="space-y-4">
                  {fetchedAtWholeSite && (
                    <p className="text-xs text-muted-foreground">
                      Last updated: {new Date(fetchedAtWholeSite).toLocaleString()}
                    </p>
                  )}
                  {!wholeSiteData.gsc_connected && (
                    <p className="text-sm text-amber-600 dark:text-amber-400">
                      Connect Google Search Console to see site-wide performance.
                    </p>
                  )}
                  <div className="text-sm text-muted-foreground">
                    {wholeSiteData.from} → {wholeSiteData.to}
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded bg-muted/50 p-3">
                      <div className="text-2xl font-bold text-foreground">
                        {wholeSiteData.organic_clicks}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Organic clicks
                      </div>
                    </div>
                    <div className="rounded bg-muted/50 p-3">
                      <div className="text-2xl font-bold text-foreground">
                        {wholeSiteData.organic_impressions}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Impressions
                      </div>
                    </div>
                  </div>
                  <div className="rounded bg-muted/50 p-3">
                    <div className="text-sm font-medium text-foreground">
                      CTR: {wholeSiteData.ctr}% · {wholeSiteData.filtered_pages_count} pages
                    </div>
                  </div>
                  {wholeSiteData.per_page && wholeSiteData.per_page.length > 0 && (
                    <div className="max-h-32 overflow-y-auto text-xs text-muted-foreground">
                      {wholeSiteData.per_page.slice(0, 5).map((row, i) => (
                        <div key={i}>{row.url}: {row.clicks} clicks</div>
                      ))}
                      {wholeSiteData.per_page.length > 5 && (
                        <div>… and {wholeSiteData.per_page.length - 5} more</div>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-muted-foreground">
                  No data yet. Click Refetch to load overall site metrics from GSC.
                </p>
              )}
            </section>
          )}
        </div>
      )}
    </div>
  );
}
