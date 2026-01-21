// components/onboarding/URLInput.tsx
'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import api from '@/lib/api';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';

interface URLInputProps {
  onAnalyze: (url: string, identityData: any) => void;
}

interface URLFormData {
  url: string;
}

export default function URLInput({ onAnalyze }: URLInputProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<URLFormData>();

  const onSubmit = async (data: URLFormData) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await api.post('/api/run', {
        task: 'onboarding',
        user_id: '', // Will be set by backend
        params: {
          step: 'analyze',
          url: data.url,
        },
      });

      if (response.data.status === 'success' && response.data.data) {
        onAnalyze(data.url, response.data.data);
      } else {
        setError(response.data.message || 'Failed to analyze website');
      }
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to analyze website. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
          Step 1: Enter Your Business Website
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
          We'll analyze your website to extract your business information automatically.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          label="Website URL"
          type="url"
          placeholder="https://example.com"
          {...register('url', {
            required: 'Website URL is required',
            pattern: {
              value: /^https?:\/\/.+/,
              message: 'Please enter a valid URL starting with http:// or https://',
            },
          })}
          error={errors.url?.message}
        />

        <Button type="submit" isLoading={isLoading} className="w-full">
          Analyze Website
        </Button>
      </form>
    </div>
  );
}
