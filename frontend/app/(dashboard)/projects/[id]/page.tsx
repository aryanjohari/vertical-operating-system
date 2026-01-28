// app/(dashboard)/projects/[id]/page.tsx
"use client";

import { useState, useEffect } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { PipelineStats, NextStep, Entity, LeadGenStats } from "@/lib/types";
import ProjectStatus from "@/components/project/ProjectStatus";
import Pipeline from "@/components/project/Pipeline";
import LeadGenDashboard from "@/components/leadgen/LeadGenDashboard";
import LeadGenActions from "@/components/leadgen/LeadGenActions";
import LeadsList from "@/components/leadgen/LeadsList";
import CampaignSelector from "@/components/campaigns/CampaignSelector";
import CreateCampaignModal from "@/components/campaigns/CreateCampaignModal";
import ScoutRunner from "@/components/pseo/ScoutRunner";
import StrategistRunner from "@/components/pseo/StrategistRunner";
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

  // Fetch manager data (pseo or lead_gen based on campaign)
  const {
    data: managerData,
    refetch,
    isLoading,
  } = useQuery({
    queryKey: ["campaign-stats", projectId, selectedCampaignId],
    queryFn: async () => {
      if (!selectedCampaignId || !selectedCampaign) {
        return null;
      }

      const task =
        selectedCampaign.module === "pseo" ? "manager" : "lead_gen_manager";
      const response = await api.post("/api/run", {
        task: task,
        user_id: "",
        params: {
          project_id: projectId,
          campaign_id: selectedCampaignId,
          action: "dashboard_stats",
        },
      });

      if (response.data.status === "success" && response.data.data) {
        return {
          stats: response.data.data.stats,
          nextStep: response.data.data.next_step,
          module: selectedCampaign.module,
        };
      }
      return null;
    },
    enabled: !!selectedCampaignId && !!selectedCampaign,
    refetchInterval: 30000,
  });

  // Enhanced refresh function that invalidates all related queries
  const refreshAll = async () => {
    // Small delay to ensure DB writes are committed
    await new Promise((resolve) => setTimeout(resolve, 500));
    // Invalidate all related queries
    await queryClient.invalidateQueries({
      queryKey: ["campaign-stats", projectId],
    });
    await queryClient.invalidateQueries({ queryKey: ["entities", projectId] });
    // Refetch the main query
    await refetch();
  };

  const stats: PipelineStats | LeadGenStats =
    managerData?.stats ||
    (selectedCampaign?.module === "lead_gen"
      ? {
          total_leads: 0,
          avg_lead_score: 0,
          total_pipeline_value: 0,
          conversion_rate: 0,
          sources: {
            sniper: 0,
            web: 0,
            voice: 0,
            google_ads: 0,
            wordpress_form: 0,
          },
          priorities: { high: 0, medium: 0, low: 0 },
          recent_leads: [],
        }
      : {
          anchors: 0,
          kws_total: 0,
          kws_pending: 0,
          "1_unreviewed": 0,
          "2_validated": 0,
          "3_linked": 0,
          "4_imaged": 0,
          "5_ready": 0,
          "6_live": 0,
        });

  const nextStep: NextStep | undefined = managerData?.nextStep;
  const campaignModule = selectedCampaign?.module;

  // Fetch anchor locations (entities) to display - filter by campaign if pseo
  const { data: entitiesData } = useQuery({
    queryKey: ["entities", projectId, "anchor_location", selectedCampaignId],
    queryFn: async () => {
      const response = await api.get(
        `/api/entities?project_id=${projectId}&entity_type=anchor_location`,
      );
      const allEntities = response.data.entities || [];
      // Filter by campaign_id if campaign is selected and it's a pseo campaign
      if (selectedCampaignId && selectedCampaign?.module === "pseo") {
        return allEntities.filter(
          (e: Entity) => e.metadata?.campaign_id === selectedCampaignId,
        );
      }
      return allEntities;
    },
    enabled: !!selectedCampaignId,
  });

  const anchorLocations: Entity[] = entitiesData || [];

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

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="text-center">Loading campaign status...</div>
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
          <ProjectStatus stats={stats as PipelineStats} nextStep={nextStep} />

          <ScoutRunner
            projectId={projectId}
            campaignId={selectedCampaignId}
            onComplete={refreshAll}
          />

          <StrategistRunner
            projectId={projectId}
            campaignId={selectedCampaignId}
            onComplete={refreshAll}
          />

          <Card className="p-6 mt-6">
            <Pipeline
              stats={stats as PipelineStats}
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
