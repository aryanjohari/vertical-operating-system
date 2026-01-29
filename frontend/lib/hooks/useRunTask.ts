"use client";

import { useState, useCallback } from "react";
import api from "@/lib/api";
import { APP_CONFIG } from "@/lib/constants";
import type { AgentOutput, AgentContext } from "@/lib/types/agent";

type RunStatus = "idle" | "processing" | "success" | "error";

export function useRunTask(taskName: string) {
  const [result, setResult] = useState<AgentOutput | null>(null);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const run = useCallback(
    async (params: Record<string, unknown>) => {
      setIsLoading(true);
      setError(null);
      setResult(null);
      setStatus("processing");

      try {
        const response = await api.post<{
          status: string;
          data?: { context_id?: string };
          message?: string;
        }>("/api/run", {
          task: taskName,
          user_id: "",
          params,
        });

        const body = response.data;

        if (body.status === "processing" && body.data?.context_id) {
          const contextId = body.data.context_id;
          const intervalMs = APP_CONFIG.POLLING_INTERVAL;
          const maxAttempts = 60;
          let resolved = false;

          for (let attempt = 0; attempt < maxAttempts; attempt++) {
            try {
              const ctxResponse = await api.get<AgentContext>(
                `/api/context/${contextId}`,
              );
              const context = ctxResponse.data;

              if (context.data.status === "completed") {
                const out = context.data.result ?? null;
                setResult(out);
                setStatus(out?.status === "error" ? "error" : "success");
                if (out?.status === "error" && out?.message) {
                  setError(out.message);
                }
                resolved = true;
                break;
              }
              if (context.data.status === "failed") {
                const msg = context.data.result?.message ?? "Task failed";
                setError(msg);
                setStatus("error");
                resolved = true;
                break;
              }
            } catch (err: unknown) {
              const ax = err as { response?: { status?: number } };
              if (ax.response?.status === 404) {
                setError("Context expired or not found");
                setStatus("error");
                resolved = true;
                break;
              }
              throw err;
            }

            await new Promise((r) => setTimeout(r, intervalMs));
          }

          if (!resolved) {
            setError("Task timeout: Context polling exceeded max attempts");
            setStatus("error");
          }
        } else if (body.status === "success" || body.status === "complete") {
          setResult(body as unknown as AgentOutput);
          setStatus("success");
        } else {
          setStatus("error");
          setError((body as { message?: string }).message ?? "Task failed");
        }
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to run task";
        setError(message);
        setStatus("error");
      } finally {
        setIsLoading(false);
      }
    },
    [taskName],
  );

  return { run, result, status, error, isLoading };
}
