// components/onboarding/OnboardingFlow.tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useProjectStore } from '@/lib/store';
import URLInput from './URLInput';
import InterviewChat from './InterviewChat';
import Card from '@/components/ui/Card';

type Step = 'url' | 'interview';

export default function OnboardingFlow() {
  const router = useRouter();
  const { setActiveProject } = useProjectStore();
  const [step, setStep] = useState<Step>('url');
  const [url, setUrl] = useState('');
  const [identityData, setIdentityData] = useState<any>(null);

  const handleAnalyze = (analyzedUrl: string, data: any) => {
    setUrl(analyzedUrl);
    setIdentityData(data);
    setStep('interview');
  };

  const handleComplete = (projectId: string) => {
    setActiveProject(projectId);
    router.push(`/projects/${projectId}`);
  };

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
          {step === 'url' ? (
            <URLInput onAnalyze={handleAnalyze} />
          ) : (
            <div>
              <div className="mb-6">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                  Step 2: Business Interview
                </h2>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Let's learn more about your business to create the perfect setup.
                </p>
                <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                  <p className="text-sm text-blue-800 dark:text-blue-300">
                    <strong>Active Module:</strong> Apex Growth (pSEO) - Programmatic SEO for Google Maps
                  </p>
                </div>
              </div>
              <InterviewChat
                url={url}
                identityData={identityData}
                onComplete={handleComplete}
              />
            </div>
          )}
        </Card>
      </main>
    </div>
  );
}
