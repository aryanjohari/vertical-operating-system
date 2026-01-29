"use client";

const TASK_LABELS: Record<string, string> = {
  scout_anchors: "Targeting Anchors...",
  strategist_run: "Running Strategist...",
  write_pages: "Writing Pages...",
  critic_review: "Reviewing Drafts...",
  librarian_link: "Linking Sources...",
  enhance_media: "Enhancing Media...",
  enhance_utility: "Enhancing Utility...",
  publish: "Publishing...",
  analytics_audit: "Auditing Analytics...",
  manager: "Manager Running...",
  lead_gen_manager: "Lead Gen Manager...",
  sniper_agent: "Sniper Hunting...",
  sales_agent: "Sales Agent...",
  reactivator_agent: "Reactivator Running...",
  lead_scorer: "Scoring Leads...",
  system_ops_manager: "System Ops...",
  onboarding: "Onboarding...",
  health_check: "Health Check...",
  log_usage: "Logging Usage...",
  cleanup: "Cleanup...",
};

/**
 * Maps raw task name to human-readable status label.
 */
export function getAgentStatusLabel(rawStatus: string): string {
  return TASK_LABELS[rawStatus] ?? rawStatus;
}

/**
 * Hook that returns the human label for a raw agent/task status.
 */
export function useAgentStatus(rawStatus: string): string {
  return getAgentStatusLabel(rawStatus);
}
