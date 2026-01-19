// Mock authentication helpers using localStorage

const AUTH_TOKEN_KEY = "apex_auth_token";
const AUTH_USER_KEY = "apex_auth_user";

export function setAuthToken(token: string, user: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
    localStorage.setItem(AUTH_USER_KEY, user);
  }
}

export function getAuthToken(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem(AUTH_TOKEN_KEY);
  }
  return null;
}

export function getAuthUser(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem(AUTH_USER_KEY);
  }
  return null;
}

export function clearAuth() {
  if (typeof window !== "undefined") {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
  }
}

export function isAuthenticated(): boolean {
  return !!getAuthToken();
}
