import { z } from "zod";

export const onboardingSchema = z.object({
  // Step 1: Identity
  businessName: z.string().min(1, "Business name is required"),
  niche: z.string().min(1, "Niche is required"),
  // Step 2: Contact
  phone: z.string().optional(),
  email: z.string().email("Invalid email").optional().or(z.literal("")),
  address: z.string().optional(),
  // Step 3: Voice
  tone: z.enum(["professional", "balanced", "casual"]).default("balanced"),
});

export type OnboardingFormValues = z.infer<typeof onboardingSchema>;
