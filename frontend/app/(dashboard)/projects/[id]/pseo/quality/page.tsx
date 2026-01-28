"use client";

import { useParams, useSearchParams } from "next/navigation";
import QualityWorkbench from "@/components/pseo/QualityWorkbench";
import PseoTabs from "@/components/pseo/PseoTabs";

export default function PseoQualityPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = params.id as string;
  const campaignId = (searchParams?.get("campaign") || "") as string;

  if (!campaignId) {
    return (
      <div className="p-8">
        <div className="text-center text-sm text-gray-600 dark:text-gray-400">
          Select a campaign from the dashboard to use Quality Gate.
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <PseoTabs
        projectId={projectId}
        campaignId={campaignId}
        current="quality"
      />
      <QualityWorkbench projectId={projectId} campaignId={campaignId} />
    </div>
  );
}

