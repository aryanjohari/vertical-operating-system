"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { PulseStats } from "@/lib/types";

interface PseoPulseProps {
  projectId: string;
  campaignId: string;
  onRefresh?: () => void;
}

const STAGES: {
  key: keyof PulseStats;
  label: string;
  route: "intel" | "strategy" | "quality" | null;
  icon: string;
}[] = [
  { key: "anchors", label: "Anchors Found", route: "intel", icon: "📍" },
  { key: "keywords", label: "Keywords Strategy", route: "strategy", icon: "🔑" },
  { key: "drafts", label: "Drafts Written", route: "quality", icon: "📝" },
  { key: "needs_review", label: "Review Needed", route: "quality", icon: "🔍" },
  { key: "published", label: "Published", route: null, icon: "✅" },
];

export default function PseoPulse({
  projectId,
  campaignId,
  onRefresh,
}: PseoPulseProps) {
  const router = useRouter();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["pulse-stats", projectId, campaignId],
    queryFn: async () => {
      const response = await api.post("/api/run", {
        task: "manager",
        user_id: "",
        params: {
          project_id: projectId,
          campaign_id: campaignId,
          action: "pulse_stats",
        },
      });
      if (response.data.status === "success" && response.data.data?.pulse) {
        return response.data.data.pulse as PulseStats;
      }
      return {
        anchors: 0,
        keywords: 0,
        drafts: 0,
        needs_review: 0,
        published: 0,
      } as PulseStats;
    },
    enabled: !!projectId && !!campaignId,
    refetchInterval: 30000,
  });

  const pulse: PulseStats = data ?? {
    anchors: 0,
    keywords: 0,
    drafts: 0,
    needs_review: 0,
    published: 0,
  };

  const handleStageClick = (route: "intel" | "strategy" | "quality" | null) => {
    if (!route) return;
    const q = new URLSearchParams({ campaign: campaignId });
    router.push(`/projects/${projectId}/pseo/${route}?${q.toString()}`);
  };

  if (isLoading) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400">
        Loading Pulse…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          pSEO Pulse
        </h2>
        {typeof onRefresh === "function" && (
          <button
            type="button"
            onClick={() => {
              refetch();
              onRefresh?.();
            }}
            className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
          >
            Refresh
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-3 md:gap-4">
        {STAGES.map(({ key, label, route, icon }) => {
          const value = pulse[key];
          const clickable = route != null;
          return (
            <button
              key={key}
              type="button"
              onClick={() => handleStageClick(route)}
              disabled={!clickable}
              className={`
                flex min-w-[140px] flex-1 basis-[140px] flex-col items-center
                rounded-xl border-2 p-4 text-left transition
                ${
                  clickable
                    ? "cursor-pointer border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/50 dark:border-gray-700 dark:bg-gray-800 dark:hover:border-blue-600 dark:hover:bg-blue-900/20"
                    : "cursor-default border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-800/80"
                }
              `}
            >
              <span className="mb-1 text-2xl">{icon}</span>
              <span className="text-sm font-medium text-gray-900 dark:text-white">
                {label}
              </span>
              <span className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
                {value}
              </span>
              {clickable && (
                <span className="mt-1 text-xs text-blue-600 dark:text-blue-400">
                  View →
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
