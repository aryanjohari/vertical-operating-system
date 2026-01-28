// components/settings/DNAEditor.tsx
"use client";

import { useState, useEffect } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { DNAConfig } from "@/lib/types";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Card from "@/components/ui/Card";

interface DNAEditorProps {
  projectId: string;
}

export default function DNAEditor({ projectId }: DNAEditorProps) {
  const queryClient = useQueryClient();
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { data: dnaData, isLoading } = useQuery({
    queryKey: ["dna-config", projectId],
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
    getValues,
    setValue,
    watch,
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
    name: "brand_brain.key_differentiators" as any,
  });

  const {
    fields: knowledgeNuggets,
    append: appendKnowledgeNugget,
    remove: removeKnowledgeNugget,
  } = useFieldArray({
    control,
    name: "brand_brain.knowledge_nuggets" as any,
  });

  const {
    fields: objections,
    append: appendObjection,
    remove: removeObjection,
  } = useFieldArray({
    control,
    name: "brand_brain.common_objections" as any,
  });

  const {
    fields: forbiddenTopics,
    append: appendForbiddenTopic,
    remove: removeForbiddenTopic,
  } = useFieldArray({
    control,
    name: "brand_brain.forbidden_topics" as any,
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
      setSuccessMessage("DNA configuration saved successfully!");
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ["dna-config", projectId] });
      setTimeout(() => setSuccessMessage(null), 3000);
    },
    onError: (error: any) => {
      setErrorMessage(
        error.response?.data?.detail || "Failed to save DNA configuration",
      );
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
            {...register("identity.business_name", {
              required: "Business name is required",
            })}
            error={errors.identity?.business_name?.message}
          />
          <Input
            label="Niche"
            {...register("identity.niche", { required: "Niche is required" })}
            error={errors.identity?.niche?.message}
          />
          <Input
            label="Website"
            type="url"
            {...register("identity.website")}
            error={errors.identity?.website?.message}
          />
          <Input
            label="Schema Type"
            {...register("identity.schema_type")}
            error={errors.identity?.schema_type?.message}
            placeholder="LocalBusiness, Plumber, LegalService, etc."
          />
          <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Used for JSON-LD structured data. Options: LocalBusiness, Plumber,
            LegalService, Locksmith, etc.
          </div>
          <div className="grid grid-cols-3 gap-4">
            <Input
              label="Phone"
              {...register("identity.contact.phone")}
              error={errors.identity?.contact?.phone?.message}
            />
            <Input
              label="Email"
              type="email"
              {...register("identity.contact.email")}
              error={errors.identity?.contact?.email?.message}
            />
            <Input
              label="Address"
              {...register("identity.contact.address")}
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
            {...register("brand_brain.voice_tone")}
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
              onClick={() => appendDifferentiator("")}
            >
              Add Differentiator
            </Button>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Knowledge Nuggets
              <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
                (Insider secrets that build instant trust)
              </span>
            </label>
            {knowledgeNuggets.map((field, index) => (
              <div key={field.id} className="flex gap-2 mb-2">
                <input
                  {...register(`brand_brain.knowledge_nuggets.${index}`)}
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                  placeholder="e.g., Police cannot force you to unlock your phone"
                />
                <Button
                  type="button"
                  variant="danger"
                  onClick={() => removeKnowledgeNugget(index)}
                >
                  Remove
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="secondary"
              onClick={() => appendKnowledgeNugget("")}
            >
              Add Knowledge Nugget
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
              onClick={() => appendObjection("")}
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
              onClick={() => appendForbiddenTopic("")}
            >
              Add Forbidden Topic
            </Button>
          </div>
        </div>
      </Card>

      {/* Module Toggles */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
          Module Toggles
        </h2>
        <div className="space-y-4">
          <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg mb-4">
            <p className="text-sm text-blue-800 dark:text-blue-300">
              <strong>Note:</strong> Module-specific configurations are managed
              in Campaigns. Enable modules here to allow campaign creation.
            </p>
          </div>

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              {...register("modules.local_seo.enabled")}
              className="w-4 h-4"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Enable pSEO Module (Apex Growth)
            </span>
          </label>

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              {...register("modules.lead_gen.enabled")}
              className="w-4 h-4"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Enable Lead Gen Module (Apex Connect)
            </span>
          </label>

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              {...register("modules.admin.enabled")}
              className="w-4 h-4"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Enable Admin Module
            </span>
          </label>
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
