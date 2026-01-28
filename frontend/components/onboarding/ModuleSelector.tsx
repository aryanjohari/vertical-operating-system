// components/onboarding/ModuleSelector.tsx
"use client";

import { useState } from "react";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";

interface ModuleSelectorProps {
  onSelect: (modules: string[]) => void;
  initialSelection?: string[];
}

export default function ModuleSelector({
  onSelect,
  initialSelection = [],
}: ModuleSelectorProps) {
  const [selectedModules, setSelectedModules] =
    useState<string[]>(initialSelection);

  const modules = [
    {
      id: "pseo",
      name: "Apex Growth (pSEO)",
      description:
        "Programmatic SEO for Google Maps dominance through automated content generation",
      icon: "📈",
    },
    {
      id: "lead_gen",
      name: "Apex Connect (Lead Gen)",
      description:
        "Active lead generation, instant connection, and lead nurturing",
      icon: "🎯",
    },
  ];

  const toggleModule = (moduleId: string) => {
    setSelectedModules((prev) =>
      prev.includes(moduleId)
        ? prev.filter((id) => id !== moduleId)
        : [...prev, moduleId],
    );
  };

  const handleContinue = () => {
    if (selectedModules.length === 0) {
      alert("Please select at least one module to continue.");
      return;
    }
    onSelect(selectedModules);
  };

  return (
    <Card>
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
          Step 3: Select Modules
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Choose which modules you'd like to enable for your project. You can
          create campaigns for each module.
        </p>
      </div>

      <div className="space-y-4 mb-6">
        {modules.map((module) => (
          <div
            key={module.id}
            onClick={() => toggleModule(module.id)}
            className={`
              p-4 border-2 rounded-lg cursor-pointer transition-all
              ${
                selectedModules.includes(module.id)
                  ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                  : "border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600"
              }
            `}
          >
            <div className="flex items-start gap-3">
              <div className="text-2xl">{module.icon}</div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <input
                    type="checkbox"
                    checked={selectedModules.includes(module.id)}
                    onChange={() => toggleModule(module.id)}
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                  />
                  <h3 className="font-semibold text-gray-900 dark:text-white">
                    {module.name}
                  </h3>
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-400 ml-6">
                  {module.description}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end">
        <Button
          onClick={handleContinue}
          disabled={selectedModules.length === 0}
        >
          Continue to Campaign Setup
        </Button>
      </div>
    </Card>
  );
}
