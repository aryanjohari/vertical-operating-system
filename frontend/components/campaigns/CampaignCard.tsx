// components/campaigns/CampaignCard.tsx
"use client";

import Card from "@/components/ui/Card";

interface Campaign {
  id: string;
  name: string;
  module: "pseo" | "lead_gen";
  status: string;
  stats?: any;
  created_at?: string;
}

interface CampaignCardProps {
  campaign: Campaign;
  isSelected?: boolean;
  onClick: () => void;
}

export default function CampaignCard({
  campaign,
  isSelected,
  onClick,
}: CampaignCardProps) {
  const statusColors: Record<string, string> = {
    DRAFT: "bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200",
    ACTIVE:
      "bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-400",
    MINING: "bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-400",
    CLUSTERING:
      "bg-purple-100 dark:bg-purple-900/20 text-purple-800 dark:text-purple-400",
    WRITING:
      "bg-yellow-100 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-400",
    PUBLISHING:
      "bg-orange-100 dark:bg-orange-900/20 text-orange-800 dark:text-orange-400",
    COMPLETED:
      "bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-400",
    PAUSED: "bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200",
    ERROR: "bg-red-100 dark:bg-red-900/20 text-red-800 dark:text-red-400",
  };

  const moduleIcons = {
    pseo: "📈",
    lead_gen: "🎯",
  };

  const moduleNames = {
    pseo: "Apex Growth (pSEO)",
    lead_gen: "Apex Connect (Lead Gen)",
  };

  return (
    <Card
      className={`p-4 cursor-pointer transition-all ${
        isSelected
          ? "border-2 border-blue-500 bg-blue-50 dark:bg-blue-900/20"
          : "border border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600"
      }`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{moduleIcons[campaign.module]}</span>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">
              {campaign.name}
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {moduleNames[campaign.module]}
            </p>
          </div>
        </div>
        <span
          className={`px-2 py-1 rounded text-xs font-medium ${
            statusColors[campaign.status] || statusColors.DRAFT
          }`}
        >
          {campaign.status}
        </span>
      </div>
      {campaign.stats && (
        <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
          <div className="flex gap-4 text-xs text-gray-600 dark:text-gray-400">
            {campaign.module === "pseo" && campaign.stats.pages_built && (
              <span>{campaign.stats.pages_built} pages</span>
            )}
            {campaign.module === "pseo" && campaign.stats.keywords && (
              <span>{campaign.stats.keywords} keywords</span>
            )}
            {campaign.module === "lead_gen" && campaign.stats.total_leads && (
              <span>{campaign.stats.total_leads} leads</span>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
