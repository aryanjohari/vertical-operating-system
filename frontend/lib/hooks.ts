// lib/hooks.ts
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from './store';
import { auth } from './auth';

export function useAuth() {
  const router = useRouter();
  const { user, token, setAuth, clearAuth } = useAuthStore();

  useEffect(() => {
    // Sync with localStorage on mount
    const storedToken = auth.getToken();
    const storedUserId = auth.getUserId();
    if (storedToken && storedUserId && !user) {
      setAuth({ id: storedUserId }, storedToken);
    }
  }, [user, setAuth]);

  const login = (userId: string, token: string) => {
    auth.setToken(token);
    auth.setUserId(userId);
    setAuth({ id: userId }, token);
  };

  const logout = () => {
    auth.removeToken();
    clearAuth();
    router.push('/login');
  };

  const isAuthenticated = auth.isAuthenticated();

  return {
    user,
    token,
    login,
    logout,
    isAuthenticated,
  };
}

export function useRequireAuth() {
  const { isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  return isAuthenticated;
}
