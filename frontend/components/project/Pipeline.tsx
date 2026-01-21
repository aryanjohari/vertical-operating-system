// components/project/Pipeline.tsx
'use client';

import { PipelineStats } from '@/lib/types';
import AgentButton from './AgentButton';

interface PipelineProps {
  stats: PipelineStats;
  projectId: string;
  onRefresh: () => void;
}

const pipelineStages = [
  {
    key: 'scout_anchors',
    label: 'Scout',
    description: 'Find locations',
    stage: '1',
    countKey: 'anchors' as keyof PipelineStats,
  },
  {
    key: 'strategist_run',
    label: 'Strategist',
    description: 'Generate keywords',
    stage: '2',
    countKey: 'kws_total' as keyof PipelineStats,
  },
  {
    key: 'write_pages',
    label: 'Writer',
    description: 'Create content',
    stage: '3',
    countKey: '1_unreviewed' as keyof PipelineStats,
  },
  {
    key: 'critic_review',
    label: 'Critic',
    description: 'Quality check',
    stage: '4',
    countKey: '2_validated' as keyof PipelineStats,
  },
  {
    key: 'librarian_link',
    label: 'Librarian',
    description: 'Add links',
    stage: '5',
    countKey: '3_linked' as keyof PipelineStats,
  },
  {
    key: 'enhance_media',
    label: 'Media',
    description: 'Add images',
    stage: '6',
    countKey: '4_imaged' as keyof PipelineStats,
  },
  {
    key: 'enhance_utility',
    label: 'Utility',
    description: 'Build tools',
    stage: '7',
    countKey: '5_ready' as keyof PipelineStats,
  },
  {
    key: 'publish',
    label: 'Publisher',
    description: 'Publish content',
    stage: '8',
    countKey: '6_live' as keyof PipelineStats,
  },
  {
    key: 'analytics_audit',
    label: 'Analytics',
    description: 'Feedback loop',
    stage: '9',
    countKey: '6_live' as keyof PipelineStats,
  },
];

export default function Pipeline({ stats, projectId, onRefresh }: PipelineProps) {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900 dark:text-white">pSEO Pipeline</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-3 gap-4">
        {pipelineStages.map((stage, index) => {
          const count = stats[stage.countKey] || 0;
          const hasItems = count > 0;

          return (
            <div
              key={stage.key}
              className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 border-2 ${
                hasItems
                  ? 'border-blue-200 dark:border-blue-800'
                  : 'border-gray-200 dark:border-gray-700'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-semibold text-gray-500 dark:text-gray-400">
                      {stage.stage}
                    </span>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                      {stage.label}
                    </h3>
                  </div>
                  <p className="text-xs text-gray-600 dark:text-gray-400">{stage.description}</p>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-gray-900 dark:text-white">{count}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-500">items</div>
                </div>
              </div>
              
              <AgentButton
                agentKey={stage.key}
                label={stage.label}
                projectId={projectId}
                onComplete={onRefresh}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
