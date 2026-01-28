// components/campaigns/CampaignSelector.tsx
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import Button from "@/components/ui/Button";

interface Campaign {
  id: string;
  name: string;
  module: "pseo" | "lead_gen";
  status: string;
  stats?: any;
}

interface CampaignSelectorProps {
  projectId: string;
  selectedCampaignId?: string;
  onSelect: (campaignId: string) => void;
  onCreateClick: () => void;
}

export default function CampaignSelector({
  projectId,
  selectedCampaignId,
  onSelect,
  onCreateClick,
}: CampaignSelectorProps) {
  const { data: campaignsData, isLoading } = useQuery({
    queryKey: ["campaigns", projectId],
    queryFn: async () => {
      const response = await api.get(`/api/projects/${projectId}/campaigns`);
      return response.data.campaigns as Campaign[];
    },
  });

  const campaigns = (campaignsData || []).filter(
    (c) => c.module === "pseo",
  );

  if (isLoading) {
    return (
      <div className="text-sm text-gray-600 dark:text-gray-400">
        Loading campaigns...
      </div>
    );
  }

  if (campaigns.length === 0) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-600 dark:text-gray-400">
          No campaigns
        </span>
        <Button onClick={onCreateClick} size="sm">
          Create Campaign
        </Button>
      </div>
    );
  }

  const selectedCampaign =
    campaigns.find((c) => c.id === selectedCampaignId) || campaigns[0];

  return (
    <div className="flex items-center gap-2">
      <select
        value={selectedCampaignId || selectedCampaign?.id || ""}
        onChange={(e) => onSelect(e.target.value)}
        className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {campaigns.map((campaign) => (
          <option key={campaign.id} value={campaign.id}>
            {campaign.name} ({campaign.module === "pseo" ? "pSEO" : "Lead Gen"})
          </option>
        ))}
      </select>
      <Button onClick={onCreateClick} size="sm" variant="secondary">
        + New
      </Button>
    </div>
  );
}
