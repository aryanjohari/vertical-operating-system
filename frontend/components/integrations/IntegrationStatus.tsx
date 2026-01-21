// components/integrations/IntegrationStatus.tsx
'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import Card from '@/components/ui/Card';

interface IntegrationStatusProps {
  projectId: string;
}

export default function IntegrationStatus({ projectId }: IntegrationStatusProps) {
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      const response = await api.get('/api/settings');
      return response.data;
    },
  });

  const hasWordPress = settings?.wp_url && settings?.wp_user;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
      <Card className={`p-4 ${hasWordPress ? 'border-green-500' : 'border-yellow-500'} border-2`}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">WordPress</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {hasWordPress ? 'Connected' : 'Not configured'}
            </p>
          </div>
          <div
            className={`w-3 h-3 rounded-full ${
              hasWordPress ? 'bg-green-500' : 'bg-yellow-500'
            }`}
          />
        </div>
      </Card>

      <Card className="p-4 border-gray-300 dark:border-gray-700 border-2">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">Google Search Console</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Check connection status
            </p>
          </div>
          <div className="w-3 h-3 rounded-full bg-gray-400" />
        </div>
      </Card>
    </div>
  );
}
