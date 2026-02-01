"use client";

import React, { useMemo, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import {
  campaignWizardSchema,
  campaignFormValuesToConfig,
  type CampaignFormValues,
} from "@/lib/schemas/campaign";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { Switch } from "@/components/ui/Switch";
import FormInput from "@/components/forms/FormInput";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";

interface CampaignWizardProps {
  projectId: string;
}

const defaultValues: Partial<CampaignFormValues> = {
  name: "",
  service: "",
  city: "",
  competitorPricing: false,
  regulatoryData: false,
  enableCallBridge: false,
  destinationPhone: "",
};

export default function CampaignWizard({ projectId }: CampaignWizardProps) {
  const router = useRouter();
  const [testSampleResult, setTestSampleResult] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    control,
    formState: { errors, isSubmitting },
  } = useForm<CampaignFormValues>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(campaignWizardSchema) as any,
    defaultValues,
  });

  const formValues = watch();
  const configPreview = useMemo(() => {
    const values = {
      ...defaultValues,
      ...formValues,
    } as CampaignFormValues;
    if (!values.service && !values.city) return {};
    return campaignFormValuesToConfig(values);
  }, [formValues]);

  const handleGenerateTestSample = async () => {
    setTestSampleResult(null);
    try {
      const res = await api.post(
        `/api/projects/${projectId}/campaigns/test-run`,
        { config: configPreview }
      ).catch(() => null);
      if (res?.data) {
        setTestSampleResult(JSON.stringify(res.data, null, 2));
      } else {
        setTestSampleResult(
          "Test run endpoint not yet available. Config validated. Full test run coming soon."
        );
      }
    } catch {
      setTestSampleResult(
        "Test run endpoint not yet available. Config validated. Full test run coming soon."
      );
    }
  };

  const onSubmit = async (values: CampaignFormValues) => {
    const config = campaignFormValuesToConfig(values);
    const { data } = await api.post(
      `/api/projects/${projectId}/campaigns`,
      { name: values.name, module: "lead_gen", config }
    );
    if (data?.campaign_id) {
      router.push("/dashboard");
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-[600px]">
      {/* Left: Form */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold text-foreground mb-4">
          Mission Launcher
        </h2>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          <Tabs defaultValue="targeting" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="targeting">Targeting</TabsTrigger>
              <TabsTrigger value="intel">Intel</TabsTrigger>
              <TabsTrigger value="leadgen">Lead Gen</TabsTrigger>
            </TabsList>
            <TabsContent value="targeting" className="space-y-4 pt-4">
              <FormInput
                label="Campaign Name"
                name="name"
                register={register}
                error={errors.name}
                placeholder="e.g. Bail Hamilton"
              />
              <FormInput
                label="Service"
                name="service"
                register={register}
                error={errors.service}
                placeholder="e.g. Bail"
              />
              <FormInput
                label="City"
                name="city"
                register={register}
                error={errors.city}
                placeholder="e.g. Hamilton"
              />
            </TabsContent>
            <TabsContent value="intel" className="space-y-4 pt-4">
              <div className="flex items-center justify-between rounded-lg border border-border p-4">
                <label
                  htmlFor="competitorPricing"
                  className="text-sm font-medium text-foreground"
                >
                  Competitor Pricing
                </label>
                <Controller
                  name="competitorPricing"
                  control={control}
                  render={({ field }) => (
                    <Switch
                      id="competitorPricing"
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  )}
                />
              </div>
              <div className="flex items-center justify-between rounded-lg border border-border p-4">
                <label
                  htmlFor="regulatoryData"
                  className="text-sm font-medium text-foreground"
                >
                  Regulatory Data
                </label>
                <Controller
                  name="regulatoryData"
                  control={control}
                  render={({ field }) => (
                    <Switch
                      id="regulatoryData"
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  )}
                />
              </div>
            </TabsContent>
            <TabsContent value="leadgen" className="space-y-4 pt-4">
              <div className="flex items-center justify-between rounded-lg border border-border p-4">
                <label
                  htmlFor="enableCallBridge"
                  className="text-sm font-medium text-foreground"
                >
                  Enable Call Bridge
                </label>
                <Controller
                  name="enableCallBridge"
                  control={control}
                  render={({ field }) => (
                    <Switch
                      id="enableCallBridge"
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  )}
                />
              </div>
              {formValues.enableCallBridge && (
                <FormInput
                  label="Destination Phone"
                  name="destinationPhone"
                  register={register}
                  error={errors.destinationPhone}
                  type="tel"
                  placeholder="+1 234 567 8900"
                />
              )}
            </TabsContent>
          </Tabs>

          <div className="flex flex-wrap gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="secondary"
              onClick={handleGenerateTestSample}
            >
              Generate Test Sample
            </Button>
            <Button type="submit" isLoading={isSubmitting}>
              Launch Campaign
            </Button>
          </div>
        </form>
      </Card>

      {/* Right: Live JSON Preview */}
      <Card className="p-6 flex flex-col">
        <h3 className="text-sm font-medium text-muted-foreground mb-2">
          Config Preview
        </h3>
        <pre className="flex-1 overflow-auto rounded-lg border border-border bg-muted/30 p-4 text-xs font-mono text-foreground">
          {JSON.stringify(configPreview, null, 2)}
        </pre>
        {testSampleResult && (
          <div className="mt-4 rounded-lg border border-border bg-muted/30 p-4">
            <p className="text-xs font-medium text-muted-foreground mb-2">
              Test Sample Result
            </p>
            <pre className="text-xs font-mono text-foreground whitespace-pre-wrap">
              {testSampleResult}
            </pre>
          </div>
        )}
      </Card>
    </div>
  );
}
