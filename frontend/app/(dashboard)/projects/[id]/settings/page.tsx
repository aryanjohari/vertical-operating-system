// app/(dashboard)/projects/[id]/settings/page.tsx
'use client';

import { useParams } from 'next/navigation';
import DNAEditor from '@/components/settings/DNAEditor';

export default function SettingsPage() {
  const params = useParams();
  const projectId = params.id as string;

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          Project Settings
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Edit your project DNA configuration
        </p>
      </div>

      <DNAEditor projectId={projectId} />
    </div>
  );
}
