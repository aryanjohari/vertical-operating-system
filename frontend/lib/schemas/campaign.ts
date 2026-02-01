import { z } from "zod";

export const campaignWizardSchema = z
  .object({
    name: z.string().min(1, "Campaign name is required"),
    // Step 1: Targeting
    service: z.string().min(1, "Service is required"),
    city: z.string().min(1, "City is required"),
    // Step 2: Intel
    competitorPricing: z.boolean().default(false),
    regulatoryData: z.boolean().default(false),
    // Step 3: Lead Gen
    enableCallBridge: z.boolean().default(false),
    destinationPhone: z.string().optional(),
  })
  .refine(
    (data) => {
      if (data.enableCallBridge) {
        return !!data.destinationPhone?.trim();
      }
      return true;
    },
    { message: "Phone is required when Call Bridge is enabled", path: ["destinationPhone"] }
  );

export type CampaignFormValues = z.infer<typeof campaignWizardSchema>;

/** Build backend config shape from form values */
export function campaignFormValuesToConfig(values: CampaignFormValues): Record<string, unknown> {
  return {
    module: "lead_gen",
    targeting: {
      service_focus: values.service,
      geo_targets: [values.city],
    },
    intel: {
      competitor_pricing: values.competitorPricing,
      regulatory_data: values.regulatoryData,
    },
    sales_bridge: values.enableCallBridge
      ? {
          enabled: true,
          destination_phone: values.destinationPhone?.trim() || "",
        }
      : { enabled: false },
  };
}
