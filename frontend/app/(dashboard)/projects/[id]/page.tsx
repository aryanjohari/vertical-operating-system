// app/(dashboard)/projects/[id]/page.tsx
'use client';

import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { PipelineStats } from '@/lib/types';
import ProjectStatus from '@/components/project/ProjectStatus';
import Pipeline from '@/components/project/Pipeline';
import Card from '@/components/ui/Card';

export default function ProjectDashboardPage() {
  const params = useParams();
  const projectId = params.id as string;

  const { data: managerData, refetch, isLoading } = useQuery({
    queryKey: ['pipeline-stats', projectId],
    queryFn: async () => {
      const response = await api.post('/api/run', {
        task: 'manager',
        user_id: '',
        params: {
          project_id: projectId,
        },
      });

      if (response.data.status === 'success' && response.data.data?.stats) {
        return response.data.data.stats as PipelineStats;
      }
      return null;
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const stats: PipelineStats = managerData || {
    anchors: 0,
    kws_total: 0,
    kws_pending: 0,
    '1_unreviewed': 0,
    '2_validated': 0,
    '3_linked': 0,
    '4_imaged': 0,
    '5_ready': 0,
    '6_live': 0,
  };

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="text-center">Loading pipeline status...</div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          Project Dashboard
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Monitor and control your pSEO pipeline
        </p>
      </div>

      <ProjectStatus stats={stats} />

      <Card className="p-6">
        <Pipeline stats={stats} projectId={projectId} onRefresh={() => refetch()} />
      </Card>
    </div>
  );
}
