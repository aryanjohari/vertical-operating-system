"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useParams } from "next/navigation";
import {
  getProjectConfig,
  updateProjectConfig,
} from "@/lib/api";
import { cn } from "@/lib/utils";

function setNested(
  obj: Record<string, unknown>,
  path: string[],
  value: unknown
): void {
  let current: Record<string, unknown> = obj;
  for (let i = 0; i < path.length - 1; i++) {
    const key = path[i];
    if (!(key in current) || typeof current[key] !== "object") {
      current[key] = {};
    }
    current = current[key] as Record<string, unknown>;
  }
  current[path[path.length - 1]] = value;
}

function getNested(
  obj: Record<string, unknown>,
  path: string[]
): unknown {
  let current: unknown = obj;
  for (const key of path) {
    if (current == null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}

export default function SettingsPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const agencyName =
    (getNested(config, ["identity", "business_name"]) as string) ?? "";
  const citiesRaw = getNested(config, ["targeting", "geo_targets", "cities"]);
  const targetCity = Array.isArray(citiesRaw)
    ? (citiesRaw[0] as string) ?? ""
    : (config.target_city as string) ?? "";
  const twilioNumber =
    (getNested(config, [
      "modules",
      "lead_gen",
      "sales_bridge",
      "destination_phone",
    ]) as string) ?? "";

  const loadConfig = async () => {
    const data = await getProjectConfig(projectId);
    setConfig(data);
  };

  useEffect(() => {
    loadConfig()
      .catch(() => setConfig({}))
      .finally(() => setLoading(false));
  }, [projectId]);

  const updateForm = (
    agency: string,
    city: string,
    twilio: string
  ) => {
    const next = JSON.parse(JSON.stringify(config));
    setNested(next, ["identity", "business_name"], agency);
    if (!next.identity) next.identity = {};
    (next.identity as Record<string, unknown>).business_name = agency;

    if (!next.targeting) next.targeting = {};
    if (!(next.targeting as Record<string, unknown>).geo_targets)
      (next.targeting as Record<string, unknown>).geo_targets = {};
    ((next.targeting as Record<string, unknown>).geo_targets as Record<string, unknown>).cities = city ? [city] : [];

    if (!next.modules) next.modules = {};
    if (!(next.modules as Record<string, unknown>).lead_gen)
      (next.modules as Record<string, unknown>).lead_gen = {};
    if (!((next.modules as Record<string, unknown>).lead_gen as Record<string, unknown>).sales_bridge)
      ((next.modules as Record<string, unknown>).lead_gen as Record<string, unknown>).sales_bridge = {};
    (((next.modules as Record<string, unknown>).lead_gen as Record<string, unknown>).sales_bridge as Record<string, unknown>).destination_phone = twilio;

    setConfig(next);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateProjectConfig(projectId, config);
      await loadConfig();
      toast.success("DNA configuration saved.");
    } catch {
      toast.error("Failed to save configuration.", {
        style: {
          background: "hsl(0 100% 60% / 0.2)",
          borderColor: "hsl(0 100% 60%)",
        },
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="glass-panel animate-pulse space-y-4 p-6">
            <div className="h-4 w-24 rounded bg-muted" />
            <div className="h-10 rounded bg-muted" />
            <div className="h-4 w-28 rounded bg-muted" />
            <div className="h-10 rounded bg-muted" />
            <div className="h-4 w-32 rounded bg-muted" />
            <div className="h-10 rounded bg-muted" />
          </div>
          <div className="glass-panel animate-pulse p-6">
            <div className="h-64 rounded bg-muted" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="acid-text text-2xl font-bold text-foreground">
          DNA Lab
        </h1>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="acid-glow rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {saving ? "Saving..." : "Save"}
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Left: Form */}
        <div className="glass-panel space-y-4 p-6">
          <h2 className="text-sm font-medium text-muted-foreground">
            Project Config
          </h2>
          <div>
            <label
              htmlFor="agency-name"
              className="block text-sm font-medium text-foreground"
            >
              Agency Name
            </label>
            <input
              id="agency-name"
              type="text"
              value={agencyName}
              onChange={(e) =>
                updateForm(e.target.value, targetCity, twilioNumber)
              }
              placeholder="Acme Digital"
              className={cn(
                "mt-1 w-full rounded border border-border bg-muted/50 px-3 py-2 text-foreground placeholder:text-muted-foreground",
                "focus:outline-none focus:ring-2 focus:ring-primary"
              )}
            />
          </div>
          <div>
            <label
              htmlFor="target-city"
              className="block text-sm font-medium text-foreground"
            >
              Target City
            </label>
            <input
              id="target-city"
              type="text"
              value={targetCity}
              onChange={(e) =>
                updateForm(agencyName, e.target.value, twilioNumber)
              }
              placeholder="Auckland"
              className={cn(
                "mt-1 w-full rounded border border-border bg-muted/50 px-3 py-2 text-foreground placeholder:text-muted-foreground",
                "focus:outline-none focus:ring-2 focus:ring-primary"
              )}
            />
          </div>
          <div>
            <label
              htmlFor="twilio-number"
              className="block text-sm font-medium text-foreground"
            >
              Twilio Number
            </label>
            <input
              id="twilio-number"
              type="tel"
              value={twilioNumber}
              onChange={(e) =>
                updateForm(agencyName, targetCity, e.target.value)
              }
              placeholder="+64 21 123 4567"
              className={cn(
                "mt-1 w-full rounded border border-border bg-muted/50 px-3 py-2 text-foreground placeholder:text-muted-foreground",
                "focus:outline-none focus:ring-2 focus:ring-primary"
              )}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Client&apos;s mobile for Sales Bridge calls
            </p>
          </div>
        </div>

        {/* Right: Raw JSON */}
        <div className="glass-panel flex flex-col p-6">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">
            Raw JSON
          </h2>
          <pre className="min-h-[300px] flex-1 overflow-auto rounded border border-border bg-muted/30 p-4 font-mono text-xs text-foreground">
            {JSON.stringify(config, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}
