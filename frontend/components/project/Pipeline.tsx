// components/project/Pipeline.tsx
"use client";

import { useState } from "react";
import { PipelineStats } from "@/lib/types";
import AgentButton from "./AgentButton";
import Button from "@/components/ui/Button";
import api from "@/lib/api";
import { useAgentStore } from "@/lib/store";

interface PipelineProps {
  stats: PipelineStats;
  projectId: string;
  campaignId?: string;
  onRefresh: () => void;
}

const pipelineStages = [
  {
    key: "scout_anchors",
    label: "Scout",
    description: "Find locations",
    stage: "1",
    countKey: "anchors" as keyof PipelineStats,
  },
  {
    key: "strategist_run",
    label: "Strategist",
    description: "Generate keywords",
    stage: "2",
    countKey: "kws_total" as keyof PipelineStats,
  },
  {
    key: "write_pages",
    label: "Writer",
    description: "Create content",
    stage: "3",
    countKey: "1_unreviewed" as keyof PipelineStats,
  },
  {
    key: "critic_review",
    label: "Critic",
    description: "Quality check",
    stage: "4",
    countKey: "2_validated" as keyof PipelineStats,
  },
  {
    key: "librarian_link",
    label: "Librarian",
    description: "Add links",
    stage: "5",
    countKey: "3_linked" as keyof PipelineStats,
  },
  {
    key: "enhance_media",
    label: "Media",
    description: "Add images",
    stage: "6",
    countKey: "4_imaged" as keyof PipelineStats,
  },
  {
    key: "enhance_utility",
    label: "Utility",
    description: "Build tools",
    stage: "7",
    countKey: "5_ready" as keyof PipelineStats,
  },
  {
    key: "publish",
    label: "Publisher",
    description: "Publish content",
    stage: "8",
    countKey: "6_live" as keyof PipelineStats,
  },
  {
    key: "analytics_audit",
    label: "Analytics",
    description: "Feedback loop",
    stage: "9",
    countKey: "6_live" as keyof PipelineStats,
  },
];

export default function Pipeline({
  stats,
  projectId,
  campaignId,
  onRefresh,
}: PipelineProps) {
  const [isOrchestrating, setIsOrchestrating] = useState(false);
  const { isRunning, setRunning } = useAgentStore();

  const handleAutoOrchestrate = async () => {
    if (isRunning || isOrchestrating) return;

    setIsOrchestrating(true);
    setRunning(true, "auto_orchestrate");

    try {
      const response = await api.post("/api/run", {
        task: "manager",
        user_id: "",
        params: {
          project_id: projectId,
          campaign_id: campaignId,
          action: "auto_orchestrate",
        },
      });

      if (
        response.data.status === "success" ||
        response.data.status === "complete"
      ) {
        onRefresh();
      }
    } catch (error) {
      console.error("Error running orchestration:", error);
    } finally {
      setIsOrchestrating(false);
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
          pSEO Pipeline
        </h2>
        <Button
          onClick={handleAutoOrchestrate}
          variant="primary"
          disabled={isRunning || isOrchestrating}
          isLoading={isOrchestrating}
          className="flex items-center gap-2"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          {isOrchestrating ? "Orchestrating..." : "Auto Orchestrate"}
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-3 gap-4">
        {pipelineStages.map((stage, index) => {
          const count = stats[stage.countKey] || 0;
          const hasItems = count > 0;

          return (
            <div
              key={stage.key}
              className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 border-2 ${
                hasItems
                  ? "border-blue-200 dark:border-blue-800"
                  : "border-gray-200 dark:border-gray-700"
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-semibold text-gray-500 dark:text-gray-400">
                      {stage.stage}
                    </span>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                      {stage.label}
                    </h3>
                  </div>
                  <p className="text-xs text-gray-600 dark:text-gray-400">
                    {stage.description}
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-gray-900 dark:text-white">
                    {count}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-500">
                    items
                  </div>
                </div>
              </div>

              <AgentButton
                agentKey={stage.key}
                label={stage.label}
                projectId={projectId}
                campaignId={campaignId}
                onComplete={onRefresh}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
