/**
 * Source of truth for Apex Sovereign OS frontend.
 */

export const APP_CONFIG = {
  NAME: "Apex Sovereign OS",
  API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  POLLING_INTERVAL: 2000,
} as const;

export const THEME_COLORS = {
  terminalBlack: "#0a0a0a",
  terminalGreen: "#00ff9d",
  terminalAmber: "#f59e0b",
} as const;
