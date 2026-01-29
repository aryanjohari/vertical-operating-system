"use client";

import { useRunTask } from "@/lib/hooks/useRunTask";
import type { ScoutParams } from "@/lib/types/agent";

interface ScoutTerminalProps {
  projectId: string;
  campaignId: string;
}

export default function ScoutTerminal({
  projectId,
  campaignId,
}: ScoutTerminalProps) {
  const { run, result, status, error, isLoading } = useRunTask("scout_anchors");

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const params: ScoutParams = {
      project_id: projectId,
      campaign_id: campaignId,
    };
    run(params);
  };

  return (
    <div
      className="font-mono border p-4"
      style={{ borderColor: "var(--border-dim)" }}
    >
      <h2 className="text-sm opacity-80 mb-3">Scout Agent</h2>
      <form onSubmit={handleSubmit} className="space-y-2 mb-4">
        <div className="flex gap-2 items-center">
          <label className="text-xs opacity-70 w-24">Project</label>
          <input
            type="text"
            readOnly
            value={projectId}
            className="flex-1 bg-transparent border px-2 py-1 text-sm"
            style={{ borderColor: "var(--border-dim)" }}
          />
        </div>
        <div className="flex gap-2 items-center">
          <label className="text-xs opacity-70 w-24">Campaign</label>
          <input
            type="text"
            readOnly
            value={campaignId}
            className="flex-1 bg-transparent border px-2 py-1 text-sm"
            style={{ borderColor: "var(--border-dim)" }}
          />
        </div>
        <button
          type="submit"
          disabled={isLoading}
          className="mt-2 px-3 py-1 border text-sm disabled:opacity-50"
          style={{
            borderColor: "var(--border-dim)",
            color: "var(--fg-primary)",
          }}
        >
          {isLoading ? "Running..." : "Run Scout"}
        </button>
      </form>
      <div className="text-xs opacity-80 mb-1">Console Output</div>
      <pre
        className="p-3 overflow-auto text-sm min-h-[80px]"
        style={{
          color: "var(--fg-primary)",
          background: "var(--bg-terminal)",
          border: "1px solid var(--border-dim)",
        }}
      >
        {error && <span className="opacity-90">{error}</span>}
        {result != null &&
          JSON.stringify(
            {
              status: result.status,
              message: result.message,
              data: result.data,
            },
            null,
            2,
          )}
        {status === "idle" && !result && !error && (
          <span className="opacity-50">—</span>
        )}
      </pre>
    </div>
  );
}
