"use client";

import { useParams, useSearchParams } from "next/navigation";
import IntelWorkbench from "@/components/pseo/IntelWorkbench";

export default function PseoIntelPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = params.id as string;
  const campaignId = (searchParams?.get("campaign") || "") as string;

  if (!campaignId) {
    return (
      <div className="p-8">
        <div className="text-center text-sm text-gray-600 dark:text-gray-400">
          Select a campaign from the dashboard to use Intel Review.
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <IntelWorkbench projectId={projectId} campaignId={campaignId} />
    </div>
  );
}

