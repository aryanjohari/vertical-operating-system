"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { runCycle, getStats, getPageDrafts, deleteEntity } from "@/lib/api";
import { getAuthUser } from "@/lib/auth";
import { useProjectContext } from "@/hooks/useProjectContext";
import { Play, Trash2, Loader2 } from "lucide-react";
import type { Entity, ManagerStats } from "@/lib/types";

export default function DashboardPage() {
  const { projectId } = useProjectContext();
  const [isRunning, setIsRunning] = useState(false);
  const [stats, setStats] = useState<ManagerStats | null>(null);
  const [pageDrafts, setPageDrafts] = useState<Entity[]>([]);
  const [logData, setLogData] = useState<any>(null);
  const [isLoadingStats, setIsLoadingStats] = useState(false);
  const [isLoadingDrafts, setIsLoadingDrafts] = useState(false);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());

  const user_id = getAuthUser() || "admin";

  // Load initial drafts only (no auto-run - stats come from manager which executes agents)
  useEffect(() => {
    loadDrafts();
  }, [projectId]);

  const loadStats = async () => {
    setIsLoadingStats(true);
    try {
      // getStats calls the manager agent, which we only want to run on button click
      const statsData = await getStats(user_id);
      setStats(statsData as ManagerStats);
    } catch (error) {
      console.error("Error loading stats:", error);
    } finally {
      setIsLoadingStats(false);
    }
  };

  const loadDrafts = async () => {
    setIsLoadingDrafts(true);
    try {
      const drafts = await getPageDrafts(user_id, projectId || undefined);
      setPageDrafts(drafts);
    } catch (error) {
      console.error("Error loading drafts:", error);
    } finally {
      setIsLoadingDrafts(false);
    }
  };

  const handleRunCycle = async () => {
    if (isRunning) return;

    setIsRunning(true);
    setLogData(null);

    try {
      const response = await runCycle(user_id);
      setLogData(response);
      
      // Refresh stats and drafts after cycle
      await loadStats();
      await loadDrafts();
    } catch (error) {
      setLogData({
        status: "error",
        message: error instanceof Error ? error.message : "Unknown error",
        timestamp: new Date().toISOString(),
      });
    } finally {
      setIsRunning(false);
    }
  };

  const handleDeletePage = async (pageId: string) => {
    if (!pageId || deletingIds.has(pageId)) return;

    if (!confirm("Are you sure you want to delete this page?")) {
      return;
    }

    setDeletingIds((prev) => new Set(prev).add(pageId));

    try {
      const success = await deleteEntity(pageId, user_id);
      if (success) {
        setPageDrafts((prev) => prev.filter((draft) => draft.id !== pageId));
      } else {
        alert("Failed to delete page");
      }
    } catch (error) {
      console.error("Error deleting page:", error);
      alert("Error deleting page");
    } finally {
      setDeletingIds((prev) => {
        const next = new Set(prev);
        next.delete(pageId);
        return next;
      });
    }
  };

  const getSlug = (draft: Entity): string => {
    if (draft.metadata?.slug) return draft.metadata.slug;
    if (draft.name) {
      return draft.name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "");
    }
    return "untitled";
  };

  return (
    <div className="p-4 md:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header with RUN CYCLE Button */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold text-purple-400">Manual Control Cockpit</h1>
            <p className="text-slate-400 mt-1">pSEO Pipeline Management</p>
          </div>
          <Button
            onClick={handleRunCycle}
            disabled={isRunning}
            size="lg"
            className="bg-purple-600 hover:bg-purple-700 text-white shadow-neon-purple w-full sm:w-auto"
          >
            {isRunning ? (
              <>
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Play className="w-5 h-5 mr-2" />
                RUN CYCLE
              </>
            )}
          </Button>
        </div>

        {/* Pipeline Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="border-purple-500/30 bg-slate-900/50">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-purple-300">
                Anchors
              </CardTitle>
              <span className="text-2xl">📍</span>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-purple-400">
                {isLoadingStats ? "..." : stats?.Locations ?? 0}
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Anchor locations
              </p>
            </CardContent>
          </Card>

          <Card className="border-purple-500/30 bg-slate-900/50">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-purple-300">
                Keywords
              </CardTitle>
              <span className="text-2xl">🔑</span>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-purple-400">
                {isLoadingStats ? "..." : stats?.Keywords ?? 0}
              </div>
              <p className="text-xs text-slate-400 mt-1">
                SEO keywords
              </p>
            </CardContent>
          </Card>

          <Card className="border-purple-500/30 bg-slate-900/50">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-purple-300">
                Drafts
              </CardTitle>
              <span className="text-2xl">📄</span>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-purple-400">
                {isLoadingStats ? "..." : stats?.Drafts ?? 0}
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Page drafts
              </p>
            </CardContent>
          </Card>

          <Card className="border-amber-400/30 bg-slate-900/50">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-amber-300">
                Ready to Publish
              </CardTitle>
              <span className="text-2xl">✅</span>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-amber-400">
                {isLoadingStats ? "..." : stats?.["5_ready"] ?? 0}
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Ready pages
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Page Drafts Table */}
        <Card className="border-purple-500/30 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="text-purple-400">Page Drafts</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoadingDrafts ? (
              <div className="text-center py-8 text-slate-400">
                <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />
                Loading drafts...
              </div>
            ) : pageDrafts.length === 0 ? (
              <div className="text-center py-8 text-slate-400">
                No page drafts found
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Title</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="hidden sm:table-cell">Slug</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pageDrafts.map((draft) => (
                      <TableRow key={draft.id}>
                        <TableCell className="font-medium text-purple-300">
                          {draft.name || "Untitled Page"}
                        </TableCell>
                        <TableCell>
                          <span className="px-2 py-1 rounded text-xs bg-slate-800 text-slate-300">
                            {draft.metadata?.status || "draft"}
                          </span>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell text-slate-400 font-mono text-sm">
                          {getSlug(draft)}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => draft.id && handleDeletePage(draft.id)}
                            disabled={draft.id ? deletingIds.has(draft.id) : true}
                          >
                            {draft.id && deletingIds.has(draft.id) ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Live Log Terminal */}
        {logData && (
          <Card className="border-purple-500/30 bg-slate-900/50">
            <CardHeader>
              <CardTitle className="text-purple-400">Live Log</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="bg-slate-950 rounded-md p-4 font-mono text-sm overflow-x-auto max-h-96 overflow-y-auto">
                <pre className="text-slate-300 whitespace-pre-wrap">
                  {JSON.stringify(logData, null, 2)}
                </pre>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
