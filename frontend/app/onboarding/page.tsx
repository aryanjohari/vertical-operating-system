"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { useProjectContext } from "@/hooks/useProjectContext";

export default function OnboardingPage() {
  const router = useRouter();
  const { user } = useAuth();
  const { setProjectId } = useProjectContext();

  const handleComplete = (projectId: string) => {
    setProjectId(projectId);
    router.push("/dashboard");
  };

  const handleClose = () => {
    router.push("/dashboard");
  };

  if (!user) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
        <div className="text-center text-slate-400">
          <p>Please log in to create a new project.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 p-4 md:p-6 lg:p-8">
      <div className="max-w-4xl mx-auto">
        <OnboardingWizard
          user_id={user}
          onComplete={handleComplete}
          onClose={handleClose}
        />
      </div>
    </div>
  );
}
