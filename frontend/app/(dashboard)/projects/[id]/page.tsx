// app/(dashboard)/projects/[id]/page.tsx
'use client';

import { useParams } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { PipelineStats, NextStep, Entity } from '@/lib/types';
import ProjectStatus from '@/components/project/ProjectStatus';
import Pipeline from '@/components/project/Pipeline';
import Card from '@/components/ui/Card';

export default function ProjectDashboardPage() {
  const params = useParams();
  const projectId = params.id as string;
  const queryClient = useQueryClient();

  const { data: managerData, refetch, isLoading } = useQuery({
    queryKey: ['pipeline-stats', projectId],
    queryFn: async () => {
      const response = await api.post('/api/run', {
        task: 'manager',
        user_id: '',
        params: {
          project_id: projectId,
          action: 'dashboard_stats', // Explicitly request stats only
        },
      });

      if (response.data.status === 'success' && response.data.data) {
        return {
          stats: response.data.data.stats as PipelineStats,
          nextStep: response.data.data.next_step as NextStep | undefined,
        };
      }
      return null;
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Enhanced refresh function that invalidates all related queries
  const refreshAll = async () => {
    // Small delay to ensure DB writes are committed
    await new Promise(resolve => setTimeout(resolve, 500));
    // Invalidate all related queries
    await queryClient.invalidateQueries({ queryKey: ['pipeline-stats', projectId] });
    await queryClient.invalidateQueries({ queryKey: ['entities', projectId] });
    // Refetch the main query
    await refetch();
  };

  const stats: PipelineStats = managerData?.stats || {
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

  const nextStep: NextStep | undefined = managerData?.nextStep;

  // Fetch anchor locations (entities) to display
  const { data: entitiesData } = useQuery({
    queryKey: ['entities', projectId, 'anchor_location'],
    queryFn: async () => {
      const response = await api.get(
        `/api/entities?project_id=${projectId}&entity_type=anchor_location`
      );
      return response.data.entities || [];
    },
  });

  const anchorLocations: Entity[] = entitiesData || [];

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

      <ProjectStatus stats={stats} nextStep={nextStep} />

      {/* Anchor Locations Section */}
      {stats.anchors > 0 && (
        <Card className="p-6 mb-6">
          <div className="mb-4">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
              Anchor Locations ({stats.anchors})
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Locations found by Scout agent
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {anchorLocations.slice(0, 12).map((entity) => (
              <div
                key={entity.id}
                className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700"
              >
                <h3 className="font-medium text-gray-900 dark:text-white mb-1">
                  {entity.name}
                </h3>
                {entity.metadata?.address && (
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                    {entity.metadata.address}
                  </p>
                )}
                {entity.primary_contact && (
                  <p className="text-xs text-gray-500 dark:text-gray-500">
                    📞 {entity.primary_contact}
                  </p>
                )}
                {entity.metadata?.google_maps_url && (
                  <a
                    href={entity.metadata.google_maps_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-600 dark:text-blue-400 hover:underline mt-2 inline-block"
                  >
                    View on Google Maps →
                  </a>
                )}
              </div>
            ))}
          </div>
          {anchorLocations.length > 12 && (
            <div className="mt-4 text-center">
              <a
                href={`/projects/${projectId}/entities?filter=anchor_location`}
                className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
              >
                View all {anchorLocations.length} locations →
              </a>
            </div>
          )}
        </Card>
      )}

      <Card className="p-6">
        <Pipeline stats={stats} projectId={projectId} onRefresh={refreshAll} />
      </Card>
    </div>
  );
}
