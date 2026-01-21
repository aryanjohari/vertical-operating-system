// components/settings/DNAEditor.tsx
'use client';

import { useState, useEffect } from 'react';
import { useForm, useFieldArray } from 'react-hook-form';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { DNAConfig } from '@/lib/types';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Card from '@/components/ui/Card';

interface DNAEditorProps {
  projectId: string;
}

export default function DNAEditor({ projectId }: DNAEditorProps) {
  const queryClient = useQueryClient();
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { data: dnaData, isLoading } = useQuery({
    queryKey: ['dna-config', projectId],
    queryFn: async () => {
      const response = await api.get(`/api/projects/${projectId}/dna`);
      return response.data.config as DNAConfig;
    },
  });

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<DNAConfig>({
    defaultValues: dnaData,
  });

  const {
    fields: differentiators,
    append: appendDifferentiator,
    remove: removeDifferentiator,
  } = useFieldArray({
    control,
    name: 'brand_brain.key_differentiators',
  });

  const {
    fields: tips,
    append: appendTip,
    remove: removeTip,
  } = useFieldArray({
    control,
    name: 'brand_brain.insider_tips',
  });

  const {
    fields: objections,
    append: appendObjection,
    remove: removeObjection,
  } = useFieldArray({
    control,
    name: 'brand_brain.common_objections',
  });

  const {
    fields: forbiddenTopics,
    append: appendForbiddenTopic,
    remove: removeForbiddenTopic,
  } = useFieldArray({
    control,
    name: 'brand_brain.forbidden_topics',
  });

  const {
    fields: anchorEntities,
    append: appendAnchorEntity,
    remove: removeAnchorEntity,
  } = useFieldArray({
    control,
    name: 'modules.local_seo.scout_settings.anchor_entities',
  });

  const {
    fields: cities,
    append: appendCity,
    remove: removeCity,
  } = useFieldArray({
    control,
    name: 'modules.local_seo.scout_settings.geo_scope.cities',
  });

  const {
    fields: leadMagnets,
    append: appendLeadMagnet,
    remove: removeLeadMagnet,
  } = useFieldArray({
    control,
    name: 'modules.lead_gen.tools.lead_magnets',
  });

  useEffect(() => {
    if (dnaData) {
      reset(dnaData);
    }
  }, [dnaData, reset]);

  const updateMutation = useMutation({
    mutationFn: async (data: DNAConfig) => {
      const response = await api.put(`/api/projects/${projectId}/dna`, data);
      return response.data;
    },
    onSuccess: () => {
      setSuccessMessage('DNA configuration saved successfully!');
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ['dna-config', projectId] });
      setTimeout(() => setSuccessMessage(null), 3000);
    },
    onError: (error: any) => {
      setErrorMessage(error.response?.data?.detail || 'Failed to save DNA configuration');
      setSuccessMessage(null);
    },
  });

  const onSubmit = (data: DNAConfig) => {
    updateMutation.mutate(data);
  };

  if (isLoading) {
    return <div className="text-center py-8">Loading DNA configuration...</div>;
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      {successMessage && (
        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-400 px-4 py-3 rounded-lg">
          {successMessage}
        </div>
      )}

      {errorMessage && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg">
          {errorMessage}
        </div>
      )}

      {/* Identity Section */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
          Identity
        </h2>
        <div className="space-y-4">
          <Input
            label="Business Name"
            {...register('identity.business_name', { required: 'Business name is required' })}
            error={errors.identity?.business_name?.message}
          />
          <Input
            label="Niche"
            {...register('identity.niche', { required: 'Niche is required' })}
            error={errors.identity?.niche?.message}
          />
          <Input
            label="Website"
            type="url"
            {...register('identity.website')}
            error={errors.identity?.website?.message}
          />
          <div className="grid grid-cols-3 gap-4">
            <Input
              label="Phone"
              {...register('identity.contact.phone')}
              error={errors.identity?.contact?.phone?.message}
            />
            <Input
              label="Email"
              type="email"
              {...register('identity.contact.email')}
              error={errors.identity?.contact?.email?.message}
            />
            <Input
              label="Address"
              {...register('identity.contact.address')}
              error={errors.identity?.contact?.address?.message}
            />
          </div>
        </div>
      </Card>

      {/* Brand Brain Section */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
          Brand Brain
        </h2>
        <div className="space-y-4">
          <Input
            label="Voice Tone"
            {...register('brand_brain.voice_tone')}
            error={errors.brand_brain?.voice_tone?.message}
          />

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Key Differentiators
            </label>
            {differentiators.map((field, index) => (
              <div key={field.id} className="flex gap-2 mb-2">
                <input
                  {...register(`brand_brain.key_differentiators.${index}`)}
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
                <Button
                  type="button"
                  variant="danger"
                  onClick={() => removeDifferentiator(index)}
                >
                  Remove
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="secondary"
              onClick={() => appendDifferentiator('')}
            >
              Add Differentiator
            </Button>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Insider Tips
            </label>
            {tips.map((field, index) => (
              <div key={field.id} className="flex gap-2 mb-2">
                <input
                  {...register(`brand_brain.insider_tips.${index}`)}
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
                <Button
                  type="button"
                  variant="danger"
                  onClick={() => removeTip(index)}
                >
                  Remove
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="secondary"
              onClick={() => appendTip('')}
            >
              Add Tip
            </Button>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Common Objections
            </label>
            {objections.map((field, index) => (
              <div key={field.id} className="flex gap-2 mb-2">
                <input
                  {...register(`brand_brain.common_objections.${index}`)}
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
                <Button
                  type="button"
                  variant="danger"
                  onClick={() => removeObjection(index)}
                >
                  Remove
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="secondary"
              onClick={() => appendObjection('')}
            >
              Add Objection
            </Button>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Forbidden Topics
            </label>
            {forbiddenTopics.map((field, index) => (
              <div key={field.id} className="flex gap-2 mb-2">
                <input
                  {...register(`brand_brain.forbidden_topics.${index}`)}
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
                <Button
                  type="button"
                  variant="danger"
                  onClick={() => removeForbiddenTopic(index)}
                >
                  Remove
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="secondary"
              onClick={() => appendForbiddenTopic('')}
            >
              Add Forbidden Topic
            </Button>
          </div>
        </div>
      </Card>

      {/* pSEO Module */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
          Apex Growth (pSEO)
        </h2>
        <div className="space-y-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              {...register('modules.local_seo.enabled')}
              className="w-4 h-4"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">Enable pSEO Module</span>
          </label>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Anchor Entities
            </label>
            {anchorEntities.map((field, index) => (
              <div key={field.id} className="flex gap-2 mb-2">
                <input
                  {...register(`modules.local_seo.scout_settings.anchor_entities.${index}`)}
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                  placeholder="e.g., Courts, Prisons"
                />
                <Button
                  type="button"
                  variant="danger"
                  onClick={() => removeAnchorEntity(index)}
                >
                  Remove
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="secondary"
              onClick={() => appendAnchorEntity('')}
            >
              Add Anchor Entity
            </Button>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Cities (Geo Scope)
            </label>
            {cities.map((field, index) => (
              <div key={field.id} className="flex gap-2 mb-2">
                <input
                  {...register(`modules.local_seo.scout_settings.geo_scope.cities.${index}`)}
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                  placeholder="e.g., Auckland"
                />
                <Button
                  type="button"
                  variant="danger"
                  onClick={() => removeCity(index)}
                >
                  Remove
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="secondary"
              onClick={() => appendCity('')}
            >
              Add City
            </Button>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Publisher CMS"
              {...register('modules.local_seo.publisher_settings.cms')}
            />
            <Input
              label="Publisher URL"
              {...register('modules.local_seo.publisher_settings.url')}
            />
            <Input
              label="Publisher Username"
              {...register('modules.local_seo.publisher_settings.username')}
            />
          </div>
        </div>
      </Card>

      {/* Lead Gen Module */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
          Apex Connect (Lead Gen)
        </h2>
        <div className="space-y-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              {...register('modules.lead_gen.enabled')}
              className="w-4 h-4"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">Enable Lead Gen Module</span>
          </label>

          <Input
            label="Forwarding Number"
            {...register('modules.lead_gen.voice_agent.forwarding_number')}
          />
          <Input
            label="Greeting"
            {...register('modules.lead_gen.voice_agent.greeting')}
          />

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Lead Magnets
            </label>
            {leadMagnets.map((field, index) => (
              <div key={field.id} className="flex gap-2 mb-2">
                <input
                  {...register(`modules.lead_gen.tools.lead_magnets.${index}`)}
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                  placeholder="e.g., Cost Calculator"
                />
                <Button
                  type="button"
                  variant="danger"
                  onClick={() => removeLeadMagnet(index)}
                >
                  Remove
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="secondary"
              onClick={() => appendLeadMagnet('')}
            >
              Add Lead Magnet
            </Button>
          </div>
        </div>
      </Card>

      <div className="flex justify-end gap-4">
        <Button
          type="button"
          variant="secondary"
          onClick={() => reset(dnaData)}
          disabled={!isDirty}
        >
          Reset
        </Button>
        <Button
          type="submit"
          isLoading={updateMutation.isPending}
          disabled={!isDirty}
        >
          Save Changes
        </Button>
      </div>
    </form>
  );
}
