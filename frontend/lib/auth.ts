// lib/auth.ts
const TOKEN_KEY = 'apex_token';
const USER_ID_KEY = 'apex_user_id';

export const auth = {
  getToken: (): string | null => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(TOKEN_KEY);
  },

  setToken: (token: string): void => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(TOKEN_KEY, token);
  },

  removeToken: (): void => {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_ID_KEY);
  },

  getUserId: (): string | null => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(USER_ID_KEY);
  },

  setUserId: (userId: string): void => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(USER_ID_KEY, userId);
  },

  isAuthenticated: (): boolean => {
    return auth.getToken() !== null;
  },
};
