"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Shell from "@/components/layout/Shell";
import ScoutTerminal from "@/components/agents/ScoutTerminal";

export default function ProjectDashboardPage() {
  const params = useParams();
  const projectId = (params?.id as string) ?? "";
  const [campaignId, setCampaignId] = useState("");

  return (
    <Shell>
      <div
        className="grid gap-4 font-mono h-full"
        style={{
          gridTemplateColumns: "1fr 1fr",
          gridTemplateRows: "auto 1fr",
          gridTemplateAreas: `
            "pipeline stats"
            "logs logs"
          `,
        }}
      >
        <section
          className="border p-4"
          style={{
            gridArea: "pipeline",
            borderColor: "var(--border-dim)",
          }}
        >
          <h2 className="text-sm opacity-80 mb-2">Active Pipeline</h2>
          <div className="mb-3">
            <label className="text-xs opacity-70 block mb-1">
              Campaign ID (required for Scout)
            </label>
            <input
              type="text"
              value={campaignId}
              onChange={(e) => setCampaignId(e.target.value)}
              placeholder="e.g. cmp_xxxxxxxxxx"
              className="w-full bg-transparent border px-2 py-1 text-sm"
              style={{ borderColor: "var(--border-dim)" }}
            />
          </div>
          {projectId && campaignId ? (
            <ScoutTerminal projectId={projectId} campaignId={campaignId} />
          ) : (
            <p className="text-xs opacity-60">
              Enter a campaign ID above to run Scout.
            </p>
          )}
        </section>
        <section
          className="border p-4"
          style={{
            gridArea: "stats",
            borderColor: "var(--border-dim)",
          }}
        >
          <h2 className="text-sm opacity-80 mb-2">Stats</h2>
          <p className="text-xs opacity-60">Placeholder</p>
        </section>
        <section
          className="border p-4 min-h-[200px]"
          style={{
            gridArea: "logs",
            borderColor: "var(--border-dim)",
          }}
        >
          <h2 className="text-sm opacity-80 mb-2">Live Logs</h2>
          <p className="text-xs opacity-60">Placeholder</p>
        </section>
      </div>
    </Shell>
  );
}
