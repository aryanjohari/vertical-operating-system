// components/onboarding/OnboardingFlow.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useProjectStore } from "@/lib/store";
import URLInput from "./URLInput";
import InterviewChat from "./InterviewChat";
import ModuleSelector from "./ModuleSelector";
import CampaignCreator from "./CampaignCreator";
import Card from "@/components/ui/Card";

type Step = "url" | "interview" | "modules" | "campaigns";

export default function OnboardingFlow() {
  const router = useRouter();
  const { setActiveProject } = useProjectStore();
  const [step, setStep] = useState<Step>("url");
  const [url, setUrl] = useState("");
  const [identityData, setIdentityData] = useState<any>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [selectedModules, setSelectedModules] = useState<string[]>([]);
  const [createdCampaigns, setCreatedCampaigns] = useState<string[]>([]);
  const [currentCampaignIndex, setCurrentCampaignIndex] = useState(0);

  const handleAnalyze = (analyzedUrl: string, data: any) => {
    setUrl(analyzedUrl);
    setIdentityData(data);
    setStep("interview");
  };

  const handleDNAComplete = (newProjectId: string) => {
    setProjectId(newProjectId);
    setStep("modules");
  };

  const handleModuleSelect = (modules: string[]) => {
    setSelectedModules(modules);
    if (modules.length > 0) {
      setStep("campaigns");
      setCurrentCampaignIndex(0);
    }
  };

  const handleCampaignComplete = (campaignId: string) => {
    setCreatedCampaigns((prev) => [...prev, campaignId]);

    // Move to next module campaign or finish
    if (currentCampaignIndex < selectedModules.length - 1) {
      setCurrentCampaignIndex(currentCampaignIndex + 1);
    } else {
      // All campaigns created, redirect to project
      if (projectId) {
        setActiveProject(projectId);
        router.push(`/projects/${projectId}`);
      }
    }
  };

  const handleSkipCampaign = () => {
    // Skip current campaign and move to next
    if (currentCampaignIndex < selectedModules.length - 1) {
      setCurrentCampaignIndex(currentCampaignIndex + 1);
    } else {
      // All campaigns done (or skipped), redirect
      if (projectId) {
        setActiveProject(projectId);
        router.push(`/projects/${projectId}`);
      }
    }
  };

  const getModuleInfo = (moduleId: string) => {
    const modules: Record<string, { name: string; id: "pseo" | "lead_gen" }> = {
      local_seo: { name: "Apex Growth (pSEO)", id: "pseo" },
      pseo: { name: "Apex Growth (pSEO)", id: "pseo" },
      lead_gen: { name: "Apex Connect (Lead Gen)", id: "lead_gen" },
    };
    return (
      modules[moduleId] || {
        name: moduleId,
        id: moduleId as "pseo" | "lead_gen",
      }
    );
  };

  const currentModule = selectedModules[currentCampaignIndex];
  const moduleInfo = currentModule ? getModuleInfo(currentModule) : null;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Project Onboarding
          </h1>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Card>
          {step === "url" ? (
            <URLInput onAnalyze={handleAnalyze} />
          ) : step === "interview" ? (
            <div>
              <div className="mb-6">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                  Step 2: Business Interview
                </h2>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Let's learn more about your business to create the perfect
                  setup.
                </p>
              </div>
              <InterviewChat
                url={url}
                identityData={identityData}
                onComplete={handleDNAComplete}
              />
            </div>
          ) : step === "modules" ? (
            <ModuleSelector
              onSelect={handleModuleSelect}
              initialSelection={selectedModules}
            />
          ) : step === "campaigns" && projectId && moduleInfo ? (
            <div>
              <div className="mb-6">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                  Step 4: Campaign Setup ({currentCampaignIndex + 1} of{" "}
                  {selectedModules.length})
                </h2>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Configure your {moduleInfo.name} campaign. You can skip this
                  and configure it later.
                </p>
              </div>
              <CampaignCreator
                projectId={projectId}
                module={moduleInfo.id}
                moduleName={moduleInfo.name}
                onComplete={handleCampaignComplete}
                onSkip={handleSkipCampaign}
              />
            </div>
          ) : null}
        </Card>
      </main>
    </div>
  );
}
