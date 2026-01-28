// components/campaigns/CreateCampaignModal.tsx
"use client";

import { useState } from "react";
import Modal from "@/components/ui/Modal";
import CampaignCreator from "@/components/onboarding/CampaignCreator";
import Button from "@/components/ui/Button";

interface CreateCampaignModalProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  onComplete: (campaignId: string) => void;
}

export default function CreateCampaignModal({
  projectId,
  isOpen,
  onClose,
  onComplete,
}: CreateCampaignModalProps) {
  const [selectedModule, setSelectedModule] = useState<"pseo" | null>(null);
  const [campaignName, setCampaignName] = useState("");

  const modules = [
    {
      id: "pseo" as const,
      name: "Apex Growth (pSEO)",
      description: "Programmatic SEO for Google Maps dominance",
      icon: "📈",
    },
  ];

  const handleModuleSelect = (module: "pseo") => {
    setSelectedModule(module);
    if (!campaignName) {
      const moduleInfo = modules.find((m) => m.id === module);
      setCampaignName(`${moduleInfo?.name} Campaign`);
    }
  };

  const handleCampaignComplete = (campaignId: string) => {
    onComplete(campaignId);
    // Reset state
    setSelectedModule(null);
    setCampaignName("");
    onClose();
  };

  const handleClose = () => {
    setSelectedModule(null);
    setCampaignName("");
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Create Campaign">
      {!selectedModule ? (
        <div className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Select a module to create a campaign for:
          </p>
          <div className="space-y-3">
            {modules.map((module) => (
              <div
                key={module.id}
                onClick={() => handleModuleSelect(module.id)}
                className="p-4 border-2 border-gray-200 dark:border-gray-700 rounded-lg cursor-pointer hover:border-blue-500 transition-colors"
              >
                <div className="flex items-start gap-3">
                  <span className="text-2xl">{module.icon}</span>
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 dark:text-white mb-1">
                      {module.name}
                    </h3>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {module.description}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="flex justify-end gap-2 mt-6">
            <Button onClick={handleClose} variant="secondary">
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <p className="text-sm text-blue-800 dark:text-blue-300">
              <strong>Creating:</strong>{" "}
              {modules.find((m) => m.id === selectedModule)?.name}
            </p>
          </div>
          <CampaignCreator
            projectId={projectId}
            module={selectedModule}
            moduleName={
              modules.find((m) => m.id === selectedModule)?.name || ""
            }
            onComplete={handleCampaignComplete}
            onSkip={handleClose}
          />
        </div>
      )}
    </Modal>
  );
}
