// components/integrations/GSCSetup.tsx
'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import api from '@/lib/api';
import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';

interface GSCSetupProps {
  projectId: string;
}

export default function GSCSetup({ projectId }: GSCSetupProps) {
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const testMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post('/api/run', {
        task: 'analytics_audit',
        user_id: '',
        params: {
          project_id: projectId,
          test: true, // Test mode
        },
      });
      return response.data;
    },
    onSuccess: (data) => {
      if (data.status === 'skipped') {
        setTestResult({
          success: false,
          message: 'GSC credentials not found. Please upload service_account.json to the server.',
        });
      } else if (data.status === 'error') {
        setTestResult({
          success: false,
          message: data.message || 'GSC connection failed',
        });
      } else {
        setTestResult({
          success: true,
          message: 'GSC connection successful!',
        });
      }
    },
    onError: (error: any) => {
      setTestResult({
        success: false,
        message: error.response?.data?.message || 'Failed to test GSC connection',
      });
    },
  });

  return (
    <Card className="p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        Google Search Console Integration
      </h3>

      {testResult && (
        <div
          className={`mb-4 px-4 py-3 rounded-lg ${
            testResult.success
              ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-400'
              : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400'
          }`}
        >
          {testResult.message}
        </div>
      )}

      <div className="space-y-4">
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
          <h4 className="font-semibold text-blue-900 dark:text-blue-300 mb-2">
            Setup Instructions:
          </h4>
          <ol className="list-decimal list-inside space-y-2 text-sm text-blue-800 dark:text-blue-300">
            <li>Go to Google Cloud Console and create a service account</li>
            <li>Enable Google Search Console API</li>
            <li>Download the service account JSON key</li>
            <li>Upload the file as <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">service_account.json</code> to your server</li>
            <li>Or set the <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">GSC_SERVICE_ACCOUNT_FILE</code> environment variable</li>
            <li>Grant the service account access to your GSC property</li>
          </ol>
        </div>

        <Button
          onClick={() => testMutation.mutate()}
          isLoading={testMutation.isPending}
        >
          Test GSC Connection
        </Button>
      </div>
    </Card>
  );
}
