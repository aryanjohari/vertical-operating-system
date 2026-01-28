// components/project/Sidebar.tsx
"use client";

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { useProjectStore } from "@/lib/store";
import ProjectSelector from "@/components/dashboard/ProjectSelector";
import CampaignCard from "@/components/campaigns/CampaignCard";
import CreateCampaignModal from "@/components/campaigns/CreateCampaignModal";
import Button from "@/components/ui/Button";

interface SidebarProps {
  projectId: string;
}

export default function Sidebar({ projectId }: SidebarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { setActiveProject } = useProjectStore();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // Fetch entities for asset counts
  const { data: entitiesData } = useQuery({
    queryKey: ["entities", projectId],
    queryFn: async () => {
      const response = await api.get(`/api/entities?project_id=${projectId}`);
      return response.data.entities || [];
    },
  });

  const entities = entitiesData || [];

  // Fetch campaigns
  const { data: campaignsData, refetch: refetchCampaigns } = useQuery({
    queryKey: ["campaigns", projectId],
    queryFn: async () => {
      const response = await api.get(`/api/projects/${projectId}/campaigns`);
      return response.data.campaigns || [];
    },
  });

  const campaigns = (campaignsData || []).filter(
    (c: any) => c.module === "pseo",
  );

  // Count entities by type (scoped to campaigns if available)
  const entityCounts = {
    anchor_location: entities.filter(
      (e: any) => e.entity_type === "anchor_location",
    ).length,
    seo_keyword: entities.filter((e: any) => e.entity_type === "seo_keyword")
      .length,
    page_draft: entities.filter((e: any) => e.entity_type === "page_draft")
      .length,
    lead: entities.filter((e: any) => e.entity_type === "lead").length,
  };

  const navItems = [
    {
      name: "Dashboard",
      href: `/projects/${projectId}`,
      icon: (
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
          />
        </svg>
      ),
    },
    {
      name: "Settings",
      href: `/projects/${projectId}/settings`,
      icon: (
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
          />
        </svg>
      ),
    },
    {
      name: "Integrations",
      href: `/projects/${projectId}/integrations`,
      icon: (
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
          />
        </svg>
      ),
    },
    {
      name: "Entities",
      href: `/projects/${projectId}/entities`,
      icon: (
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"
          />
        </svg>
      ),
    },
  ];

  const isActive = (href: string) => pathname === href;

  return (
    <div className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 h-screen flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Project
          </h2>
          <a
            href="/dashboard"
            onClick={(e) => {
              e.preventDefault();
              router.push("/dashboard");
            }}
            className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
          >
            All Projects
          </a>
        </div>
        <div className="mt-2">
          <ProjectSelector />
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => (
          <a
            key={item.href}
            href={item.href}
            onClick={(e) => {
              e.preventDefault();
              router.push(item.href);
            }}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
              isActive(item.href)
                ? "bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400"
                : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
            }`}
          >
            {item.icon}
            <span>{item.name}</span>
          </a>
        ))}
      </nav>

      {/* Campaigns Section */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
            Campaigns
          </h3>
          <Button
            onClick={() => setIsCreateModalOpen(true)}
            size="sm"
            variant="secondary"
            className="text-xs"
          >
            + New
          </Button>
        </div>
        {campaigns.length === 0 ? (
          <div className="text-center py-4">
            <p className="text-xs text-gray-600 dark:text-gray-400 mb-2">
              No campaigns yet
            </p>
            <Button
              onClick={() => setIsCreateModalOpen(true)}
              size="sm"
              className="w-full"
            >
              Create Campaign
            </Button>
          </div>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {campaigns.map((campaign: any) => (
              <div
                key={campaign.id}
                className="p-2 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer"
                onClick={() => {
                  router.push(`/projects/${projectId}?campaign=${campaign.id}`);
                }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-gray-900 dark:text-white truncate">
                      {campaign.name}
                    </p>
                    <p className="text-xs text-gray-600 dark:text-gray-400">
                      📈 pSEO
                    </p>
                  </div>
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded ${
                      campaign.status === "ACTIVE"
                        ? "bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-400"
                        : campaign.status === "DRAFT"
                          ? "bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200"
                          : "bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-400"
                    }`}
                  >
                    {campaign.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Database Assets */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-700">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
          Database Assets
        </h3>
        <div className="space-y-1 text-sm">
          <div className="flex justify-between px-2 py-1 text-gray-600 dark:text-gray-400">
            <span>Locations</span>
            <span className="font-medium">{entityCounts.anchor_location}</span>
          </div>
          <div className="flex justify-between px-2 py-1 text-gray-600 dark:text-gray-400">
            <span>Keywords</span>
            <span className="font-medium">{entityCounts.seo_keyword}</span>
          </div>
          <div className="flex justify-between px-2 py-1 text-gray-600 dark:text-gray-400">
            <span>Pages</span>
            <span className="font-medium">{entityCounts.page_draft}</span>
          </div>
          <div className="flex justify-between px-2 py-1 text-gray-400 dark:text-gray-600">
            <span>Leads (hidden)</span>
            <span className="font-medium">—</span>
          </div>
        </div>
      </div>

      <CreateCampaignModal
        projectId={projectId}
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onComplete={(campaignId) => {
          refetchCampaigns();
          setIsCreateModalOpen(false);
          // Optionally navigate to the new campaign
          router.push(`/projects/${projectId}?campaign=${campaignId}`);
        }}
      />
    </div>
  );
}
