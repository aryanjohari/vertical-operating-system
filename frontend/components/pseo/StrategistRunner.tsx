// components/pseo/StrategistRunner.tsx
"use client";

import { useState, useEffect } from "react";
import api, { pollContextUntilComplete } from "@/lib/api";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";

interface StrategistRunnerProps {
  projectId: string;
  campaignId: string;
  onComplete?: () => void;
}

type StrategistStatus = "idle" | "processing" | "completed" | "error";

export default function StrategistRunner({
  projectId,
  campaignId,
  onComplete,
}: StrategistRunnerProps) {
  const [status, setStatus] = useState<StrategistStatus>("idle");
  const [isLoading, setIsLoading] = useState(false);
  const [contextId, setContextId] = useState<string | null>(null);
  const [result, setResult] = useState<{
    keywords_generated: number;
    clusters?: string[];
    message?: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Poll for status if we have a contextId and status is processing
  useEffect(() => {
    if (status === "processing" && contextId) {
      // Call pollContextUntilComplete once - it handles internal polling with 5s interval
      pollContextUntilComplete(contextId, 120, 5000)
        .then((contextResult) => {
          if (contextResult) {
            if (
              contextResult.status === "success" ||
              contextResult.status === "complete"
            ) {
              setStatus("completed");
              setResult({
                keywords_generated: contextResult.data?.keywords_generated || 0,
                clusters: contextResult.data?.clusters || [],
                message: contextResult.message,
              });
              if (onComplete) {
                // Small delay to ensure DB writes are committed
                setTimeout(() => {
                  onComplete();
                }, 500);
              }
            } else {
              setStatus("error");
              setError(contextResult.message || "Strategist execution failed");
            }
          }
        })
        .catch((err: any) => {
          if (err.message?.includes("timeout")) {
            setStatus("error");
            setError(
              "Strategist execution timed out. It may still be running in the background.",
            );
          } else {
            setStatus("error");
            setError(err.message || "Failed to poll strategist status");
          }
        });
    }
  }, [status, contextId, onComplete]);

  const handleRunStrategist = async () => {
    if (isLoading || status === "processing") return;

    setIsLoading(true);
    setStatus("processing");
    setError(null);
    setResult(null);
    setContextId(null);

    try {
      const response = await api.post("/api/run", {
        task: "strategist_run",
        user_id: "", // Will be set by backend
        params: {
          project_id: projectId,
          campaign_id: campaignId,
        },
      });

      if (response.data.status === "processing") {
        const newContextId = response.data.data?.context_id;
        if (newContextId) {
          setContextId(newContextId);
          // Status will be updated by polling effect
        } else {
          setStatus("error");
          setError("No context ID received from server");
        }
      } else if (
        response.data.status === "success" ||
        response.data.status === "complete"
      ) {
        // Sync completion (unlikely for strategist, but handle it)
        setStatus("completed");
        setResult({
          keywords_generated: response.data.data?.keywords_generated || 0,
          clusters: response.data.data?.clusters || [],
          message: response.data.message,
        });
        if (onComplete) {
          setTimeout(() => {
            onComplete();
          }, 500);
        }
      } else {
        setStatus("error");
        setError(response.data.message || "Strategist execution failed");
      }
    } catch (err: any) {
      setStatus("error");
      setError(
        err.response?.data?.message || err.message || "Failed to start strategist",
      );
      console.error("Error running strategist:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setStatus("idle");
    setContextId(null);
    setResult(null);
    setError(null);
  };

  return (
    <Card className="p-6">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-1">
              Strategist Agent
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Generate revenue-ready SEO keywords from anchor locations
            </p>
          </div>
          {status === "idle" && (
            <Button
              onClick={handleRunStrategist}
              disabled={isLoading}
              isLoading={isLoading}
              variant="primary"
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
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
              Run Strategist
            </Button>
          )}
        </div>

        {status === "processing" && (
          <div className="flex items-center gap-3 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
            <svg
              className="animate-spin h-5 w-5 text-blue-600 dark:text-blue-400"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <div className="flex-1">
              <p className="text-sm font-medium text-blue-900 dark:text-blue-100">
                Strategist is running...
              </p>
              <p className="text-xs text-blue-700 dark:text-blue-300">
                Generating SEO keywords from anchor locations and validating search intent. This
                may take a few minutes.
              </p>
            </div>
          </div>
        )}

        {status === "completed" && result && (
          <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
            <div className="flex items-start justify-between mb-3">
              <div>
                <p className="text-sm font-medium text-green-900 dark:text-green-100 mb-1">
                  Strategist completed successfully!
                </p>
                {result.message && (
                  <p className="text-xs text-green-700 dark:text-green-300">
                    {result.message}
                  </p>
                )}
              </div>
              <Button onClick={handleReset} variant="ghost" className="text-xs">
                Run Again
              </Button>
            </div>
            <div className="grid grid-cols-1 gap-4 mt-4">
              <div className="bg-white dark:bg-gray-800 rounded p-3">
                <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">
                  Keywords Generated
                </p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {result.keywords_generated}
                </p>
              </div>
              {result.clusters && result.clusters.length > 0 && (
                <div className="bg-white dark:bg-gray-800 rounded p-3">
                  <p className="text-xs text-gray-600 dark:text-gray-400 mb-2">
                    Intent Clusters
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {result.clusters.slice(0, 6).map((cluster, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-1 text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded"
                      >
                        {cluster}
                      </span>
                    ))}
                    {result.clusters.length > 6 && (
                      <span className="px-2 py-1 text-xs text-gray-500 dark:text-gray-400">
                        +{result.clusters.length - 6} more
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {status === "error" && error && (
          <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-red-900 dark:text-red-100 mb-1">
                  Strategist execution failed
                </p>
                <p className="text-xs text-red-700 dark:text-red-300">
                  {error}
                </p>
              </div>
              <Button onClick={handleReset} variant="ghost" className="text-xs">
                Try Again
              </Button>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
