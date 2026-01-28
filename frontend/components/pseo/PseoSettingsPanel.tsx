"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

interface PseoSettingsPanelProps {
  projectId: string;
  campaignId: string;
}

interface PseoSettings {
  batch_size: number;
  speed_profile: "aggressive" | "balanced" | "human" | string;
}

interface DebugLogEntry {
  stage: string;
  task: string;
  status: string;
  message: string;
}

export default function PseoSettingsPanel({
  projectId,
  campaignId,
}: PseoSettingsPanelProps) {
  const queryClient = useQueryClient();
  const [isDebugOpen, setIsDebugOpen] = useState(false);

  const { data: settings, isLoading } = useQuery({
    queryKey: ["pseo-settings", projectId, campaignId],
    queryFn: async () => {
      const response = await api.post("/api/run", {
        task: "manager",
        user_id: "",
        params: {
          project_id: projectId,
          campaign_id: campaignId,
          action: "get_settings",
        },
      });
      return (response.data.data?.settings || {
        batch_size: 5,
        speed_profile: "balanced",
      }) as PseoSettings;
    },
    enabled: !!campaignId,
  });

  const [localSettings, setLocalSettings] = useState<PseoSettings>({
    batch_size: 5,
    speed_profile: "balanced",
  });

  const [debugLogs, setDebugLogs] = useState<DebugLogEntry[]>([]);

  const updateMutation = useMutation({
    mutationFn: async (payload: PseoSettings) => {
      await api.post("/api/run", {
        task: "manager",
        user_id: "",
        params: {
          project_id: projectId,
          campaign_id: campaignId,
          action: "update_settings",
          settings: payload,
        },
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["pseo-settings", projectId, campaignId],
      });
    },
  });

  const debugMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post("/api/run", {
        task: "manager",
        user_id: "",
        params: {
          project_id: projectId,
          campaign_id: campaignId,
          action: "debug_run",
        },
      });
      const logs = (response.data.data?.logs || []) as DebugLogEntry[];
      setDebugLogs(logs);
      setIsDebugOpen(true);
    },
  });

  const effectiveSettings = settings || localSettings;

  const handleBatchChange = (value: string) => {
    const numeric = parseInt(value || "0", 10);
    setLocalSettings((prev) => ({
      ...prev,
      batch_size: Number.isNaN(numeric) ? prev.batch_size : numeric,
    }));
  };

  const handleSpeedChange = (value: string) => {
    setLocalSettings((prev) => ({
      ...prev,
      speed_profile: value as PseoSettings["speed_profile"],
    }));
  };

  const handleSave = () => {
    updateMutation.mutate(localSettings);
  };

  return (
    <Card className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            PSEO Control Panel
          </h2>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Control throughput for this campaign and run a single-item debug pass.
          </p>
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Loading PSEO settings...
        </p>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                Batch Size
              </label>
              <input
                type="number"
                min={1}
                max={50}
                defaultValue={effectiveSettings.batch_size}
                onChange={(e) => handleBatchChange(e.target.value)}
                className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-500">
                Maximum pages to write per Writer/critic cycle.
              </p>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                Speed Profile
              </label>
              <select
                defaultValue={effectiveSettings.speed_profile}
                onChange={(e) => handleSpeedChange(e.target.value)}
                className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              >
                <option value="aggressive">Aggressive • ~50/hr</option>
                <option value="balanced">Balanced • ~10/hr</option>
                <option value="human">Human • ~2/hr</option>
              </select>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-500">
                Controls pacing across the pipeline to match your risk tolerance.
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-gray-700">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => debugMutation.mutate()}
              disabled={debugMutation.isPending}
              isLoading={debugMutation.isPending}
            >
              Debug Run (batch_size=1)
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSave}
              disabled={updateMutation.isPending}
              isLoading={updateMutation.isPending}
            >
              Save Settings
            </Button>
          </div>

          {isDebugOpen && (
            <div className="mt-6 rounded-lg border border-gray-200 bg-gray-50 p-4 text-xs text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100">
              <div className="mb-2 flex items-center justify-between">
                <p className="font-semibold">Debug Run Log</p>
                <button
                  type="button"
                  onClick={() => setIsDebugOpen(false)}
                  className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                >
                  Close
                </button>
              </div>
              {debugLogs.length === 0 ? (
                <p>No logs returned for this run.</p>
              ) : (
                <ul className="space-y-1">
                  {debugLogs.map((log, idx) => (
                    <li key={`${log.task}-${idx}`}>
                      <span className="font-semibold">{log.stage}</span>:{" "}
                      <span className="italic">{log.status}</span> —{" "}
                      <span>{log.message}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </>
      )}
    </Card>
  );
}

