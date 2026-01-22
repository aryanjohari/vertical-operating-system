// lib/api.ts
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { auth } from './auth';
import { AgentOutput, AgentContext } from './types';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: Inject JWT token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = auth.getToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor: Handle 401 (unauthorized)
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      auth.removeToken();
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

/**
 * Determines if a task is heavy (async) or light (sync)
 */
export const HEAVY_TASKS = [
  'sniper_agent',
  'sales_agent',
  'reactivator_agent',
  'onboarding'
];

export function isHeavyTask(task: string): boolean {
  return HEAVY_TASKS.includes(task);
}

/**
 * Polls context until task completes or times out
 * @param contextId - Context ID from processing response
 * @param maxAttempts - Maximum polling attempts (default: 60 = 2 minutes at 2s interval)
 * @param intervalMs - Polling interval in milliseconds (default: 2000)
 * @returns Final AgentOutput or null if timeout
 */
export async function pollContextUntilComplete(
  contextId: string,
  maxAttempts: number = 60,
  intervalMs: number = 2000
): Promise<AgentOutput | null> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      const response = await api.get<AgentContext>(`/api/context/${contextId}`);
      const context = response.data;
      
      if (context.data.status === 'completed') {
        return context.data.result || null;
      } else if (context.data.status === 'failed') {
        throw new Error(context.data.result?.message || 'Task failed');
      }
      
      // Still processing, wait and retry
      await new Promise(resolve => setTimeout(resolve, intervalMs));
    } catch (error: any) {
      // If context not found (expired), return null
      if (error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  }
  
  // Timeout
  throw new Error('Task timeout: Context polling exceeded max attempts');
}

export default api;
