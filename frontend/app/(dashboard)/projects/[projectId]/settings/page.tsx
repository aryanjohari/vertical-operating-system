"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getProjectConfig, getFormSchema, updateProjectConfig, getSettings, saveSettings } from "@/lib/api";
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

  const [wpUrl, setWpUrl] = useState("");
  const [wpUser, setWpUser] = useState("");
  const [wpPassword, setWpPassword] = useState("");
  const [wpSaving, setWpSaving] = useState(false);

  const loadSchemaAndConfig = useCallback(async () => {
    if (!projectId) return;
    setFetchError(null);
    try {
      const [schemaRes, config, settings] = await Promise.all([
        getFormSchema("profile"),
        getProjectConfig(projectId),
        getSettings(),
      ]);
      setSchema(schemaRes.schema);
      setDefaults((config && Object.keys(config).length > 0 ? config : schemaRes.defaults ?? {}) as Record<string, unknown>);
      setWpUrl(settings.wp_url ?? "");
      setWpUser(settings.wp_user ?? "");
      setWpPassword("");
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

  const handleSaveWordPress = useCallback(async () => {
    setWpSaving(true);
    try {
      await saveSettings({
        wp_url: wpUrl.trim(),
        wp_user: wpUser.trim(),
        wp_password: wpPassword || undefined,
      });
      setWpPassword("");
      toast.success("WordPress credentials saved.");
    } catch {
      toast.error("Failed to save WordPress credentials.");
    } finally {
      setWpSaving(false);
    }
  }, [wpUrl, wpUser, wpPassword]);

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

      <div className="glass-panel max-w-3xl space-y-4 p-6">
        <h2 className="text-lg font-semibold text-foreground">WordPress / CMS</h2>
        <p className="text-sm text-muted-foreground">
          Credentials used by the Publisher to post funnel pages to your WordPress site (wp-json/wp/v2/posts).
          Use Application Password in production. Stored securely per account.
        </p>
        <div className="grid gap-4 sm:grid-cols-1">
          <div>
            <label htmlFor="wp_url" className="mb-1 block text-sm font-medium text-foreground">
              WordPress URL
            </label>
            <input
              id="wp_url"
              type="url"
              value={wpUrl}
              onChange={(e) => setWpUrl(e.target.value)}
              placeholder="https://yoursite.com"
              className="w-full rounded border border-border bg-background px-3 py-2 text-foreground placeholder:text-muted-foreground"
            />
          </div>
          <div>
            <label htmlFor="wp_user" className="mb-1 block text-sm font-medium text-foreground">
              Username
            </label>
            <input
              id="wp_user"
              type="text"
              value={wpUser}
              onChange={(e) => setWpUser(e.target.value)}
              placeholder="WordPress username or app user"
              className="w-full rounded border border-border bg-background px-3 py-2 text-foreground placeholder:text-muted-foreground"
            />
          </div>
          <div>
            <label htmlFor="wp_password" className="mb-1 block text-sm font-medium text-foreground">
              Password / Application Password
            </label>
            <input
              id="wp_password"
              type="password"
              value={wpPassword}
              onChange={(e) => setWpPassword(e.target.value)}
              placeholder="Leave blank to keep current password"
              autoComplete="new-password"
              className="w-full rounded border border-border bg-background px-3 py-2 text-foreground placeholder:text-muted-foreground"
            />
          </div>
          <button
            type="button"
            onClick={handleSaveWordPress}
            disabled={wpSaving}
            className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {wpSaving ? "Saving…" : "Save WordPress credentials"}
          </button>
        </div>
      </div>
    </div>
  );
}
