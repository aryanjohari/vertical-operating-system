// components/leadgen/LeadGenActions.tsx
"use client";

import { useState } from "react";
import api, { pollContextUntilComplete } from "@/lib/api";
import { useAgentStore } from "@/lib/store";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Card from "@/components/ui/Card";

interface LeadGenActionsProps {
  projectId: string;
  campaignId?: string;
  onComplete?: () => void;
}

// Actions that trigger async tasks (via lead_gen_manager)
const ASYNC_ACTIONS = ["hunt_sniper", "ignite_reactivation", "instant_call"];

export default function LeadGenActions({
  projectId,
  campaignId,
  onComplete,
}: LeadGenActionsProps) {
  const { isRunning, runningAgent, setRunning, updateLastRunTime } =
    useAgentStore();
  const [isLoading, setIsLoading] = useState<string | null>(null);
  const [testCallLeadId, setTestCallLeadId] = useState("");
  const [showTestCallInput, setShowTestCallInput] = useState(false);

  const handleAction = async (
    action: string,
    additionalParams: Record<string, any> = {},
  ) => {
    if (isRunning || isLoading) return;

    setIsLoading(action);
    setRunning(true, `lead_gen_${action}`);

    try {
      const response = await api.post("/api/run", {
        task: "lead_gen_manager",
        user_id: "", // Will be set by backend
        params: {
          project_id: projectId,
          campaign_id: campaignId,
          action: action,
          ...additionalParams,
        },
      });

      // Handle async response (processing status)
      if (response.data.status === "processing") {
        const contextId = response.data.data?.context_id;
        if (contextId) {
          try {
            // Poll for completion
            const result = await pollContextUntilComplete(contextId);
            if (
              result &&
              (result.status === "success" || result.status === "complete")
            ) {
              updateLastRunTime(`lead_gen_${action}`);
              if (onComplete) {
                onComplete();
              }
              if (action === "instant_call") {
                setShowTestCallInput(false);
                setTestCallLeadId("");
              }
            } else {
              console.error(
                `Error running ${action}:`,
                result?.message || "Task failed",
              );
            }
          } catch (error) {
            console.error(`Error polling context for ${action}:`, error);
            // Show error to user
          }
        }
      } else if (
        response.data.status === "success" ||
        response.data.status === "complete"
      ) {
        // Sync action completed immediately (e.g., dashboard_stats)
        updateLastRunTime(`lead_gen_${action}`);
        if (onComplete) {
          onComplete();
        }
        if (action === "instant_call") {
          setShowTestCallInput(false);
          setTestCallLeadId("");
        }
      } else {
        console.error(`Error running ${action}:`, response.data.message);
      }
    } catch (error) {
      console.error(`Error running ${action}:`, error);
    } finally {
      setIsLoading(null);
      setRunning(false);
    }
  };

  const handleTestCall = () => {
    if (!testCallLeadId.trim()) {
      alert("Please enter a lead ID");
      return;
    }
    handleAction("instant_call", { lead_id: testCallLeadId.trim() });
  };

  const actions = [
    {
      key: "hunt_sniper",
      label: "Hunt Sniper",
      description: "Deploy sniper agent to find new leads",
      icon: (
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
      ),
      onClick: () => handleAction("hunt_sniper"),
      variant: "primary" as const,
    },
    {
      key: "ignite_reactivation",
      label: "Blast List",
      description: "Send reactivation SMS to leads",
      icon: (
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
      ),
      onClick: () => handleAction("ignite_reactivation"),
      variant: "secondary" as const,
    },
    {
      key: "instant_call",
      label: "Test Call",
      description: "Bridge a call for a specific lead",
      icon: (
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
          />
        </svg>
      ),
      onClick: () => setShowTestCallInput(!showTestCallInput),
      variant: "secondary" as const,
    },
  ];

  const isActionRunning = (actionKey: string) => {
    return isLoading === actionKey || runningAgent === `lead_gen_${actionKey}`;
  };

  return (
    <Card className="p-6">
      <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
        Lead Gen Actions
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        {actions.map((action) => (
          <div key={action.key} className="space-y-2">
            <Button
              onClick={action.onClick}
              disabled={isRunning && !isActionRunning(action.key)}
              isLoading={isActionRunning(action.key)}
              variant={action.variant}
              className="w-full flex items-center justify-center gap-2"
            >
              {action.icon}
              {isActionRunning(action.key) ? "Running..." : action.label}
            </Button>
            <p className="text-xs text-gray-600 dark:text-gray-400 text-center">
              {action.description}
            </p>
          </div>
        ))}
      </div>

      {showTestCallInput && (
        <div className="mt-4 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="space-y-3">
            <Input
              label="Lead ID"
              type="text"
              value={testCallLeadId}
              onChange={(e) => setTestCallLeadId(e.target.value)}
              placeholder="Enter lead ID to test call"
            />
            <div className="flex gap-2">
              <Button
                onClick={handleTestCall}
                disabled={
                  !testCallLeadId.trim() || isActionRunning("instant_call")
                }
                isLoading={isActionRunning("instant_call")}
                variant="primary"
                className="flex-1"
              >
                Initiate Call
              </Button>
              <Button
                onClick={() => {
                  setShowTestCallInput(false);
                  setTestCallLeadId("");
                }}
                variant="ghost"
                disabled={isActionRunning("instant_call")}
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
