// components/project/ProjectStatus.tsx
'use client';

import { PipelineStats } from '@/lib/types';
import Card from '@/components/ui/Card';

interface ProjectStatusProps {
  stats: PipelineStats;
}

export default function ProjectStatus({ stats }: ProjectStatusProps) {
  const cards = [
    {
      title: 'Locations',
      value: stats.anchors,
      icon: (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      ),
      color: 'text-blue-600 dark:text-blue-400',
    },
    {
      title: 'Keywords',
      value: stats.kws_total,
      subtitle: `${stats.kws_pending} pending`,
      icon: (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
        </svg>
      ),
      color: 'text-green-600 dark:text-green-400',
    },
    {
      title: 'Pages',
      value: stats['1_unreviewed'] + stats['2_validated'] + stats['3_linked'] + stats['4_imaged'] + stats['5_ready'] + stats['6_live'],
      subtitle: `${stats['6_live']} live`,
      icon: (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
      color: 'text-purple-600 dark:text-purple-400',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      {cards.map((card) => (
        <Card key={card.title} className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">{card.title}</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white">{card.value}</p>
              {card.subtitle && (
                <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">{card.subtitle}</p>
              )}
            </div>
            <div className={card.color}>{card.icon}</div>
          </div>
        </Card>
      ))}
    </div>
  );
}
