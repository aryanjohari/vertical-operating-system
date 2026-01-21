// components/entities/EntityForm.tsx
'use client';

import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { Entity } from '@/lib/types';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';

interface EntityFormData {
  entity_type: string;
  name: string;
  primary_contact?: string;
  metadata: string; // JSON string for editing
}

interface EntityFormProps {
  entity?: Entity;
  onSubmit: (data: Omit<EntityFormData, 'metadata'> & { metadata: Record<string, any> }) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export default function EntityForm({ entity, onSubmit, onCancel, isLoading }: EntityFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<EntityFormData>({
    defaultValues: {
      entity_type: entity?.entity_type || '',
      name: entity?.name || '',
      primary_contact: entity?.primary_contact || '',
      metadata: entity?.metadata ? JSON.stringify(entity.metadata, null, 2) : '{}',
    },
  });

  useEffect(() => {
    if (entity) {
      reset({
        entity_type: entity.entity_type,
        name: entity.name,
        primary_contact: entity.primary_contact || '',
        metadata: entity.metadata ? JSON.stringify(entity.metadata, null, 2) : '{}',
      });
    }
  }, [entity, reset]);

  const onFormSubmit = (data: EntityFormData) => {
    try {
      const metadata = JSON.parse(data.metadata || '{}');
      onSubmit({
        entity_type: data.entity_type,
        name: data.name,
        primary_contact: data.primary_contact,
        metadata,
      });
    } catch (error) {
      alert('Invalid JSON in metadata field');
    }
  };

  return (
    <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-4">
      <Input
        label="Entity Type"
        {...register('entity_type', { required: 'Entity type is required' })}
        error={errors.entity_type?.message}
        placeholder="e.g., anchor_location, seo_keyword, page_draft, lead"
      />

      <Input
        label="Name"
        {...register('name', { required: 'Name is required' })}
        error={errors.name?.message}
      />

      <Input
        label="Primary Contact"
        {...register('primary_contact')}
        error={errors.primary_contact?.message}
        placeholder="Email, phone, or URL"
      />

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Metadata (JSON)
        </label>
        <textarea
          {...register('metadata')}
          rows={8}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder='{"key": "value"}'
        />
        {errors.metadata && (
          <p className="mt-1 text-sm text-red-600 dark:text-red-400">{errors.metadata.message}</p>
        )}
      </div>

      <div className="flex justify-end gap-4">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" isLoading={isLoading}>
          {entity ? 'Update' : 'Create'}
        </Button>
      </div>
    </form>
  );
}
