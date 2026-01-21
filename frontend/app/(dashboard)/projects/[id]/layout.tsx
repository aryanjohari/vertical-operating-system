// app/(dashboard)/projects/[id]/layout.tsx
'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useProjectStore } from '@/lib/store';
import Sidebar from '@/components/project/Sidebar';
import { useAuth } from '@/lib/hooks';

export default function ProjectLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const { setActiveProject } = useProjectStore();
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    if (projectId && isAuthenticated) {
      setActiveProject(projectId);
    }
  }, [projectId, isAuthenticated, setActiveProject]);

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      <Sidebar projectId={projectId} />
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
