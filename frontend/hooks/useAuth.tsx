"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { getAuthToken, getAuthUser, clearAuth, setAuthToken, isAuthenticated } from "@/lib/auth";
import { verifyUser } from "@/lib/api";

interface AuthContextType {
  user: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Check auth on mount
    const token = getAuthToken();
    const authUser = getAuthUser();
    if (token && authUser) {
      setUser(authUser);
    }
    setIsLoading(false);
  }, []);

  const login = async (email: string, password: string): Promise<boolean> => {
    // Verify credentials against SQL database
    const result = await verifyUser(email, password);
    if (result.success && result.user_id) {
      setAuthToken(result.user_id, result.user_id);
      setUser(result.user_id);
      return true;
    }
    return false;
  };

  const logout = () => {
    clearAuth();
    setUser(null);
    router.push("/");
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

export function useRequireAuth() {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !user && pathname?.startsWith("/dashboard")) {
      router.push("/");
    }
  }, [user, isLoading, pathname, router]);

  return { user, isLoading };
}
