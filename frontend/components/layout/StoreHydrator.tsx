"use client";

import { useEffect } from "react";
import { useAppStore } from "@/store/useAppStore";

/**
 * Triggers Zustand persist rehydration on the client.
 * Required when using skipHydration to avoid SSR/localStorage mismatch.
 * Runs once on mount so AuthGuard and RedirectHome receive _hydrated.
 */
export function StoreHydrator({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    useAppStore.persist.rehydrate();
  }, []);

  return <>{children}</>;
}
