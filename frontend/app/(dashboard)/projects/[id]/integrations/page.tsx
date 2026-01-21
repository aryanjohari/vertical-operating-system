// app/(dashboard)/projects/[id]/integrations/page.tsx
'use client';

import { useParams } from 'next/navigation';
import IntegrationStatus from '@/components/integrations/IntegrationStatus';
import WordPressSetup from '@/components/integrations/WordPressSetup';
import GSCSetup from '@/components/integrations/GSCSetup';

export default function IntegrationsPage() {
  const params = useParams();
  const projectId = params.id as string;

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          Integrations
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Configure external service connections
        </p>
      </div>

      <IntegrationStatus projectId={projectId} />

      <div className="space-y-6">
        <WordPressSetup projectId={projectId} />
        <GSCSetup projectId={projectId} />
      </div>
    </div>
  );
}
