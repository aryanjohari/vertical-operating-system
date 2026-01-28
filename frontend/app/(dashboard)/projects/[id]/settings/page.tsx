// app/(dashboard)/projects/[id]/settings/page.tsx
'use client';

import { useParams, useSearchParams } from 'next/navigation';
import DNAEditor from '@/components/settings/DNAEditor';
import PseoSettingsPanel from '@/components/pseo/PseoSettingsPanel';
import Card from '@/components/ui/Card';

export default function SettingsPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = params.id as string;
  const campaignId = (searchParams?.get('campaign') || '') as string;

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          Project Settings
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Edit your project DNA configuration and per-campaign pSEO controls.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,2fr),minmax(0,1.4fr)]">
        <DNAEditor projectId={projectId} />

        <div className="space-y-4">
          {campaignId ? (
            <PseoSettingsPanel projectId={projectId} campaignId={campaignId} />
          ) : (
            <Card className="p-6 text-sm text-gray-600 dark:text-gray-400">
              Select a pSEO campaign from the main dashboard to adjust throttling
              and debug settings here.
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
