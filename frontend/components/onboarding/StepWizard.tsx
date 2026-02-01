"use client";

import React from "react";
import Button from "@/components/ui/Button";

export interface StepConfig {
  id: string;
  label: string;
}

interface StepWizardProps {
  steps: StepConfig[];
  currentStep: number;
  onNext: () => void;
  onBack: () => void;
  children: React.ReactNode;
  isLastStep?: boolean;
  isSubmitting?: boolean;
}

export default function StepWizard({
  steps,
  currentStep,
  onNext,
  onBack,
  children,
  isLastStep = false,
  isSubmitting = false,
}: StepWizardProps) {
  const progress = ((currentStep + 1) / steps.length) * 100;

  return (
    <div className="w-full space-y-6">
      {/* Progress bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm text-muted-foreground">
          <span>
            Step {currentStep + 1} of {steps.length}
          </span>
          <span>{steps[currentStep]?.label}</span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-border overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Step content */}
      <div className="min-h-[200px]">{children}</div>

      {/* Navigation */}
      <div className="flex justify-between pt-4 border-t border-border">
        <Button
          type="button"
          variant="ghost"
          onClick={onBack}
          disabled={currentStep === 0}
        >
          Back
        </Button>
        <Button
          type="button"
          onClick={onNext}
          disabled={isSubmitting}
          isLoading={isSubmitting && isLastStep}
        >
          {isLastStep ? "Submit" : "Next"}
        </Button>
      </div>
    </div>
  );
}
