// components/integrations/WordPressSetup.tsx
'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Card from '@/components/ui/Card';

interface WordPressFormData {
  wp_url: string;
  wp_user: string;
  wp_password: string;
}

interface WordPressSetupProps {
  projectId: string;
}

export default function WordPressSetup({ projectId }: WordPressSetupProps) {
  const queryClient = useQueryClient();
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      const response = await api.get('/api/settings');
      return response.data;
    },
  });

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<WordPressFormData>({
    defaultValues: {
      wp_url: settings?.wp_url || '',
      wp_user: settings?.wp_user || '',
      wp_password: '',
    },
  });

  const saveMutation = useMutation({
    mutationFn: async (data: WordPressFormData) => {
      const response = await api.post('/api/settings', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      setTestResult({ success: true, message: 'WordPress credentials saved successfully!' });
    },
    onError: (error: any) => {
      setTestResult({
        success: false,
        message: error.response?.data?.detail || 'Failed to save credentials',
      });
    },
  });

  const testConnection = async (data: WordPressFormData) => {
    setIsTesting(true);
    setTestResult(null);

    try {
      // Save credentials first
      await api.post('/api/settings', data);

      // Test by trying to publish a test page (or just check connection)
      const response = await api.post('/api/run', {
        task: 'publish',
        user_id: '',
        params: {
          project_id: projectId,
          test: true, // Flag for test mode
        },
      });

      if (response.data.status === 'success') {
        setTestResult({ success: true, message: 'Connection successful! WordPress is ready.' });
      } else {
        setTestResult({
          success: false,
          message: response.data.message || 'Connection test failed',
        });
      }
    } catch (error: any) {
      setTestResult({
        success: false,
        message: error.response?.data?.message || 'Failed to test connection',
      });
    } finally {
      setIsTesting(false);
    }
  };

  const onSubmit = (data: WordPressFormData) => {
    saveMutation.mutate(data);
  };

  if (isLoading) {
    return <div className="text-center py-4">Loading settings...</div>;
  }

  return (
    <Card className="p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        WordPress Integration
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

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          label="WordPress URL"
          type="url"
          placeholder="https://yoursite.com"
          {...register('wp_url', { required: 'WordPress URL is required' })}
          error={errors.wp_url?.message}
        />

        <Input
          label="Username"
          {...register('wp_user', { required: 'Username is required' })}
          error={errors.wp_user?.message}
        />

        <Input
          label="Password"
          type="password"
          {...register('wp_password', { required: 'Password is required' })}
          error={errors.wp_password?.message}
        />

        <div className="flex gap-4">
          <Button
            type="button"
            variant="secondary"
            onClick={handleSubmit(testConnection)}
            isLoading={isTesting}
          >
            Test Connection
          </Button>
          <Button type="submit" isLoading={saveMutation.isPending}>
            Save Credentials
          </Button>
        </div>
      </form>
    </Card>
  );
}
