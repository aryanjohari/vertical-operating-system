"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getProjectConfig, getFormSchema, updateProjectConfig } from "@/lib/api";
import { toast } from "sonner";
import { DynamicForm } from "@/components/forms/DynamicForm";
import type { FormSchema } from "@/lib/api";

export default function SettingsPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  const [schema, setSchema] = useState<FormSchema | null>(null);
  const [defaults, setDefaults] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const loadSchemaAndConfig = useCallback(async () => {
    if (!projectId) return;
    setFetchError(null);
    try {
      const [schemaRes, config] = await Promise.all([
        getFormSchema("profile"),
        getProjectConfig(projectId),
      ]);
      setSchema(schemaRes.schema);
      setDefaults((config && Object.keys(config).length > 0 ? config : schemaRes.defaults ?? {}) as Record<string, unknown>);
    } catch (e) {
      setFetchError(e instanceof Error ? e.message : "Failed to load form");
      setSchema(null);
      setDefaults({});
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadSchemaAndConfig();
  }, [loadSchemaAndConfig]);

  const handleSave = useCallback(
    async (values: Record<string, unknown>) => {
      if (!projectId) return;
      try {
        await updateProjectConfig(projectId, values);
        await loadSchemaAndConfig();
        toast.success("DNA configuration saved.");
      } catch {
        toast.error("Failed to save configuration.", {
          style: {
            background: "hsl(0 100% 60% / 0.2)",
            borderColor: "hsl(0 100% 60%)",
          },
        });
      }
    },
    [projectId, loadSchemaAndConfig]
  );

  if (loading) {
    return (
      <div className="space-y-6 p-4">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="glass-panel animate-pulse space-y-4 p-6">
            <div className="h-4 w-24 rounded bg-muted" />
            <div className="h-10 rounded bg-muted" />
            <div className="h-4 w-28 rounded bg-muted" />
            <div className="h-10 rounded bg-muted" />
          </div>
        </div>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="space-y-4 p-4">
        <p className="text-destructive">{fetchError}</p>
        <Link href={`/projects/${projectId}`} className="text-primary hover:underline">
          Back to project
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4">
      <div className="flex items-center justify-between">
        <h1 className="acid-text text-2xl font-bold text-foreground">DNA Lab</h1>
        <Link
          href={`/projects/${projectId}`}
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Project
        </Link>
      </div>

      <div className="glass-panel max-w-3xl space-y-4 p-6">
        <p className="text-sm text-muted-foreground">
          Edit project identity, brand voice, and module toggles. All values are saved to DNA (dna.custom.yaml).
        </p>
        {schema ? (
          <DynamicForm
            schema={schema}
            defaults={defaults}
            onSubmit={handleSave}
            submitLabel="Save DNA"
          />
        ) : (
          <p className="text-sm text-muted-foreground">No form schema available.</p>
        )}
      </div>
    </div>
  );
}
