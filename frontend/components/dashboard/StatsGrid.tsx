"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ManagerStats } from "@/lib/types";

interface StatsGridProps {
  stats: ManagerStats | undefined;
  isLoading: boolean;
}

export function StatsGrid({ stats, isLoading }: StatsGridProps) {
  const locations = stats?.Locations ?? 0;
  const pages = stats?.Drafts ?? 0;
  const keywords = stats?.Keywords ?? 0;

  return (
    <div className="grid gap-6 md:grid-cols-3">
      <Card className="border-purple-500/30 shadow-neon-purple">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium text-purple-300">
            Locations Found
          </CardTitle>
          <span className="text-2xl">📍</span>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold text-purple-400">
            {isLoading ? "..." : locations}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Anchor locations discovered
          </p>
        </CardContent>
      </Card>

      <Card className="border-purple-500/30 shadow-neon-purple">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium text-purple-300">
            Pages Written
          </CardTitle>
          <span className="text-2xl">📄</span>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold text-purple-400">
            {isLoading ? "..." : pages}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Landing pages drafted
          </p>
        </CardContent>
      </Card>

      <Card className="border-amber-400/30 shadow-neon-gold">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium text-amber-300">
            Leads Captured
          </CardTitle>
          <span className="text-2xl">🔑</span>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold text-amber-400">
            {isLoading ? "..." : keywords}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            SEO keywords generated
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
