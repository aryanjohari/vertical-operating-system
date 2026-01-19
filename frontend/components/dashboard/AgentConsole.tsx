"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { runAgent } from "@/lib/api";
import { getAuthUser } from "@/lib/auth";

interface LogEntry {
  timestamp: Date;
  level: "info" | "success" | "error";
  message: string;
}

export function AgentConsole() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isRunning, setIsRunning] = useState<string | null>(null);
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);

  const addLog = (level: LogEntry["level"], message: string) => {
    setLogs((prev) => [
      ...prev,
      {
        timestamp: new Date(),
        level,
        message,
      },
    ]);
  };

  const executeAgent = async (task: string, taskName: string, params: Record<string, any> = {}) => {
    if (isRunning) {
      addLog("error", `Agent "${isRunning}" is already running. Wait for it to complete.`);
      return;
    }

    setIsRunning(taskName);
    addLog("info", `[START] Launching ${taskName}...`);

    try {
      const user_id = getAuthUser() || "admin";
      let lastStatus = "running";

      // Initial request
      const result = await runAgent(task, user_id, params);
      addLog(
        result.status === "success" || result.status === "complete" ? "success" : "info",
        `[PROCESSING] ${result.message || "Agent is working..."}`
      );

      // Poll for updates if needed (for long-running tasks)
      if (result.status === "action_required" || result.status === "continue") {
        const interval = setInterval(async () => {
          try {
            const pollResult = await runAgent(task, user_id, params);
            
            if (pollResult.status !== lastStatus) {
              addLog(
                pollResult.status === "success" || pollResult.status === "complete"
                  ? "success"
                  : "info",
                `[UPDATE] ${pollResult.message || "Processing..."}`
              );
              lastStatus = pollResult.status;
            }

            if (pollResult.status === "success" || pollResult.status === "complete" || pollResult.status === "error") {
              clearInterval(interval);
              setIsRunning(null);
              setPollingInterval(null);
              addLog("success", `[COMPLETE] ${taskName} finished successfully.`);
            }
          } catch (error) {
            clearInterval(interval);
            setIsRunning(null);
            setPollingInterval(null);
            addLog("error", `[ERROR] ${error instanceof Error ? error.message : "Unknown error"}`);
          }
        }, 2500); // Poll every 2.5 seconds

        setPollingInterval(interval);
      } else if (result.status === "success" || result.status === "complete") {
        setIsRunning(null);
        addLog("success", `[COMPLETE] ${taskName} finished successfully.`);
      } else if (result.status === "error") {
        setIsRunning(null);
        addLog("error", `[ERROR] ${result.message || "Task failed"}`);
      }
    } catch (error) {
      setIsRunning(null);
      addLog("error", `[ERROR] ${error instanceof Error ? error.message : "Unknown error"}`);
    }
  };

  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [pollingInterval]);

  const clearLogs = () => {
    setLogs([]);
  };

  return (
    <div className="space-y-6">
      <div className="flex gap-2 flex-wrap">
        <Button
          onClick={() => executeAgent("scout_anchors", "Run Scout")}
          disabled={!!isRunning}
          variant="default"
        >
          Run Scout
        </Button>
        <Button
          onClick={() => executeAgent("seo_keyword", "Generate Keywords")}
          disabled={!!isRunning}
          variant="default"
        >
          Generate Keywords
        </Button>
        <Button
          onClick={() => executeAgent("write_pages", "Start Writer")}
          disabled={!!isRunning}
          variant="default"
        >
          Start Writer
        </Button>
        <Button
          onClick={() => executeAgent("enhance_media", "Fetch Images")}
          disabled={!!isRunning}
          variant="secondary"
        >
          Fetch Images
        </Button>
        <Button
          onClick={() => executeAgent("enhance_utility", "Build Tools")}
          disabled={!!isRunning}
          variant="secondary"
        >
          Build Tools
        </Button>
        <Button
          onClick={() => executeAgent("publish", "Publish")}
          disabled={!!isRunning}
          variant="outline"
        >
          Publish
        </Button>
        <Button onClick={clearLogs} variant="ghost" className="ml-auto">
          Clear Logs
        </Button>
      </div>

      <Card className="bg-slate-950 border-purple-500/30">
        <CardHeader>
          <CardTitle className="text-purple-400 font-mono text-sm">
            Agent Console
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="bg-black rounded-md p-4 h-96 overflow-y-auto font-mono text-sm">
            {logs.length === 0 ? (
              <div className="text-slate-500">No logs yet. Run an agent to see output.</div>
            ) : (
              logs.map((log, idx) => (
                <div
                  key={idx}
                  className={`mb-1 ${
                    log.level === "success"
                      ? "text-emerald-400"
                      : log.level === "error"
                      ? "text-red-400"
                      : "text-purple-300"
                  }`}
                >
                  <span className="text-slate-500">
                    [{log.timestamp.toLocaleTimeString()}]
                  </span>{" "}
                  {log.message}
                </div>
              ))
            )}
            {isRunning && (
              <div className="text-amber-400 animate-pulse mt-2">
                ⚡ {isRunning} in progress...
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
