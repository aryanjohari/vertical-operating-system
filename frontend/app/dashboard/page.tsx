"use client";

import { useManagerStatus } from "@/hooks/useManagerStatus";
import { StatsGrid } from "@/components/dashboard/StatsGrid";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function MissionControlPage() {
  const { data, isLoading, mutate } = useManagerStatus();

  const handleRefresh = () => {
    mutate();
  };

  const stats = data?.data?.stats;
  const currentStep = data?.data?.step || "active";
  const actionLabel = data?.data?.action_label;
  const description = data?.data?.description;
  const status = data?.status;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-purple-400">Mission Control</h1>
          <p className="text-slate-400 mt-1">
            Real-time operational status and metrics
          </p>
        </div>
        <Button onClick={handleRefresh} variant="outline" size="sm">
          🔄 Refresh Status
        </Button>
      </div>

      <StatsGrid stats={stats} isLoading={isLoading} />

      <Card className="border-purple-500/30 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-purple-300">Current Directive</CardTitle>
          <CardDescription className="text-slate-400">
            System status and next actions
          </CardDescription>
        </CardHeader>
        <CardContent>
          {status === "action_required" ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <Badge variant="pending">Action Required</Badge>
                <span className="text-slate-300">{data?.message}</span>
              </div>
              {description && (
                <p className="text-slate-400 text-sm">{description}</p>
              )}
              {actionLabel && (
                <p className="text-amber-400 text-sm font-medium">
                  Next: {actionLabel}
                </p>
              )}
            </div>
          ) : status === "complete" ? (
            <div className="space-y-2">
              <Badge variant="live">All Systems Nominal</Badge>
              <p className="text-slate-300">{data?.message || "Campaign is active and monitoring for new opportunities."}</p>
            </div>
          ) : status === "error" ? (
            <div className="space-y-2">
              <Badge variant="destructive">System Error</Badge>
              <p className="text-red-400">{data?.message || "An error occurred"}</p>
            </div>
          ) : (
            <div className="text-slate-400 text-sm">Loading system status...</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
