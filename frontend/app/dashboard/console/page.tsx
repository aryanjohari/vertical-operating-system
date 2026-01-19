"use client";

import { AgentConsole } from "@/components/dashboard/AgentConsole";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function AgentConsolePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-purple-400">Agent Console</h1>
        <p className="text-slate-400 mt-1">
          Execute agents and monitor real-time execution logs
        </p>
      </div>

      <AgentConsole />
    </div>
  );
}
