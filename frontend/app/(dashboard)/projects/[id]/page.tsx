// app/(dashboard)/projects/[id]/page.tsx
"use client";

import { useState, useEffect } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import CampaignSelector from "@/components/campaigns/CampaignSelector";
import CreateCampaignModal from "@/components/campaigns/CreateCampaignModal";
import PseoPulse from "@/components/pseo/PseoPulse";
import PseoTabs from "@/components/pseo/PseoTabs";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

export default function ProjectDashboardPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = params.id as string;
  const queryClient = useQueryClient();
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(
    null,
  );
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // Fetch campaigns
  const { data: campaignsData, refetch: refetchCampaigns } = useQuery({
    queryKey: ["campaigns", projectId],
    queryFn: async () => {
      const response = await api.get(`/api/projects/${projectId}/campaigns`);
      return response.data.campaigns || [];
    },
  });

  const campaigns = campaignsData || [];

  // Set selected campaign from URL or first campaign
  useEffect(() => {
    const campaignFromUrl = searchParams?.get("campaign");
    if (
      campaignFromUrl &&
      campaigns.find((c: any) => c.id === campaignFromUrl)
    ) {
      setSelectedCampaignId(campaignFromUrl);
    } else if (campaigns.length > 0 && !selectedCampaignId) {
      setSelectedCampaignId(campaigns[0].id);
    }
  }, [campaigns, searchParams, selectedCampaignId]);

  const selectedCampaign = campaigns.find(
    (c: any) => c.id === selectedCampaignId,
  );
  const campaignModule = selectedCampaign?.module;

  const refreshAll = async () => {
    await new Promise((resolve) => setTimeout(resolve, 500));
    await queryClient.invalidateQueries({
      queryKey: ["pulse-stats", projectId, selectedCampaignId],
    });
    await queryClient.invalidateQueries({ queryKey: ["entities", projectId] });
  };

  // Show empty state if no campaigns
  if (campaigns.length === 0) {
    return (
      <div className="p-8">
        <div className="max-w-2xl mx-auto text-center">
          <div className="mb-6">
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
              No Campaigns Yet
            </h1>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              Create a campaign to get started with pSEO or Lead Gen.
            </p>
          </div>
          <Card className="p-8">
            <div className="space-y-4">
              <p className="text-gray-600 dark:text-gray-400">
                Campaigns allow you to configure and run specific modules for
                your project. Each campaign has its own configuration and tracks
                its own progress.
              </p>
              <Button onClick={() => setIsCreateModalOpen(true)} size="lg">
                Create Your First Campaign
              </Button>
            </div>
          </Card>
        </div>
        <CreateCampaignModal
          projectId={projectId}
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          onComplete={(campaignId) => {
            refetchCampaigns();
            setSelectedCampaignId(campaignId);
            setIsCreateModalOpen(false);
          }}
        />
      </div>
    );
  }

  if (!selectedCampaignId || !selectedCampaign) {
    return (
      <div className="p-8">
        <div className="text-center">Select a campaign to view dashboard</div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
              {selectedCampaign.name}
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              {campaignModule === "pseo"
                ? "Monitor and control your pSEO pipeline"
                : "Monitor and control your lead generation pipeline"}
            </p>
          </div>
          <CampaignSelector
            projectId={projectId}
            selectedCampaignId={selectedCampaignId}
            onSelect={(campaignId) => {
              setSelectedCampaignId(campaignId);
              // Update URL without reload
              window.history.pushState(
                {},
                "",
                `/projects/${projectId}?campaign=${campaignId}`,
              );
            }}
            onCreateClick={() => setIsCreateModalOpen(true)}
          />
        </div>
      </div>

      {campaignModule === "pseo" ? (
        <>
          <PseoTabs
            projectId={projectId}
            campaignId={selectedCampaignId}
            current="pulse"
          />
          <Card className="p-6">
            <PseoPulse
              projectId={projectId}
              campaignId={selectedCampaignId}
              onRefresh={refreshAll}
            />
          </Card>
        </>
      ) : (
        <div className="space-y-6">
          <Card className="p-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
              Lead Gen module is currently hidden
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Existing Lead Gen campaigns remain intact on the backend, but the
              Lead Gen dashboard UI is temporarily disabled while we focus on
              the pSEO experience.
            </p>
          </Card>
        </div>
      )}

      <CreateCampaignModal
        projectId={projectId}
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onComplete={(campaignId) => {
          refetchCampaigns();
          setSelectedCampaignId(campaignId);
          setIsCreateModalOpen(false);
        }}
      />
    </div>
  );
}
