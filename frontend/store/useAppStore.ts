/**
 * Titanium OS — Global App Store
 * Auth, navigation, and UI state with localStorage persistence for auth.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types";
import { setAuthToken } from "@/lib/api";
import { login as apiLogin } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AppState {
  // Auth
  user: User | null;
  token: string | null;
  _hydrated?: boolean;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;

  // Navigation
  currentProjectId: string | null;
  currentCampaignId: string | null;
  setProject: (id: string | null) => void;
  setCampaign: (id: string | null) => void;

  // UI
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      _hydrated: false,

      login: async (email, password) => {
        try {
          const res = await apiLogin(email, password);
          if (res.success && res.token && res.user_id) {
            const user: User = { id: res.user_id };
            setAuthToken(res.token);
            set({ user, token: res.token });
            return { success: true };
          }
          return { success: false, error: "Invalid credentials" };
        } catch (e) {
          return {
            success: false,
            error: e instanceof Error ? e.message : "Login failed",
          };
        }
      },

      logout: () => {
        setAuthToken(null);
        set({ user: null, token: null });
      },

      currentProjectId: null,
      currentCampaignId: null,
      setProject: (id) => set({ currentProjectId: id }),
      setCampaign: (id) => set({ currentCampaignId: id }),

      isSidebarOpen: true,
      toggleSidebar: () => set((s) => ({ isSidebarOpen: !s.isSidebarOpen })),
    }),
    {
      name: "titanium-auth",
      partialize: (s) => ({ user: s.user, token: s.token }),
      skipHydration: true,
      onRehydrateStorage: () => (state) => {
        if (state?.token) {
          setAuthToken(state.token);
        }
        useAppStore.setState({ _hydrated: true });
      },
    }
  )
);
