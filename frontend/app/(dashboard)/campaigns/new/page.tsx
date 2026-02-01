"use client";

import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";
import Link from "next/link";
import CampaignWizard from "@/components/campaigns/CampaignWizard";
import { useProjectStore } from "@/lib/store";
import Button from "@/components/ui/Button";

export default function NewCampaignPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { activeProjectId, projects } = useProjectStore();
  const projectIdFromQuery = searchParams.get("projectId");
  const projectId = projectIdFromQuery ?? activeProjectId;

  if (!projectId) {
    return (
      <div className="max-w-2xl mx-auto py-12 px-4">
        <p className="text-muted-foreground mb-4">
          Select a project to create a campaign, or create a campaign from a
          project page.
        </p>
        {projects.length > 0 ? (
          <div className="space-y-2">
            {projects.map((p: { project_id: string; niche?: string }) => (
              <Link
                key={p.project_id}
                href={`/campaigns/new?projectId=${p.project_id}`}
                className="block p-3 rounded-lg border border-border hover:bg-muted/30 text-foreground"
              >
                {p.niche ?? p.project_id}
              </Link>
            ))}
          </div>
        ) : (
          <Button onClick={() => router.push("/onboarding")}>
            Create a project first
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto py-8 px-4">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">
          New Campaign
        </h1>
        <Button variant="ghost" onClick={() => router.push("/dashboard")}>
          Back to Dashboard
        </Button>
      </div>
      <CampaignWizard projectId={projectId} />
    </div>
  );
}
