// app/(dashboard)/projects/[id]/entities/page.tsx
'use client';

import { useParams } from 'next/navigation';
import EntityManager from '@/components/entities/EntityManager';

export default function EntitiesPage() {
  const params = useParams();
  const projectId = params.id as string;

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          Data CRM
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Manage all your entities, pages, leads, and more
        </p>
      </div>

      <EntityManager projectId={projectId} />
    </div>
  );
}
