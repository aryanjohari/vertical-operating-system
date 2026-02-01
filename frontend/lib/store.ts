// lib/store.ts
import { create } from 'zustand';
import { Project } from './types';

interface AuthStore {
  user: { id: string } | null;
  token: string | null;
  setAuth: (user: { id: string }, token: string) => void;
  clearAuth: () => void;
  hydrate: () => void;
}

interface ProjectStore {
  activeProjectId: string | null;
  projects: Project[];
  setActiveProject: (projectId: string | null) => void;
  setProjects: (projects: Project[]) => void;
  addProject: (project: Project) => void;
}

interface AgentStore {
  isRunning: boolean;
  runningAgent: string | null;
  lastRunTime: Record<string, Date>;
  setRunning: (isRunning: boolean, agent?: string | null) => void;
  updateLastRunTime: (agent: string) => void;
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  token: null,
  setAuth: (user, token) => set({ user, token }),
  clearAuth: () => set({ user: null, token: null }),
  hydrate: () => {
    if (typeof window === "undefined") return;
    const token = localStorage.getItem("apex_token");
    const userId = localStorage.getItem("apex_user_id");
    if (token && userId) set({ token, user: { id: userId } });
  },
}));

export const useProjectStore = create<ProjectStore>((set) => ({
  activeProjectId: null,
  projects: [],
  setActiveProject: (projectId) => set({ activeProjectId: projectId }),
  setProjects: (projects) => set({ projects }),
  addProject: (project) =>
    set((state) => ({
      projects: [...state.projects, project],
    })),
}));

export const useAgentStore = create<AgentStore>((set) => ({
  isRunning: false,
  runningAgent: null,
  lastRunTime: {},
  setRunning: (isRunning, agent = null) =>
    set({ isRunning, runningAgent: agent }),
  updateLastRunTime: (agent) =>
    set((state) => ({
      lastRunTime: { ...state.lastRunTime, [agent]: new Date() },
    })),
}));
