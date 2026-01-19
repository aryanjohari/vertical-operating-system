"use client";

import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { LogOut } from "lucide-react";

export function Header() {
  const { user, logout } = useAuth();

  return (
    <header className="border-b border-purple-500/20 bg-slate-950/50 px-6 py-4 flex items-center justify-between">
      <div>
        <h2 className="text-lg font-semibold text-purple-300">
          Command Center
        </h2>
        <p className="text-xs text-slate-400">{user || "Guest"}</p>
      </div>
      <Button
        onClick={logout}
        variant="ghost"
        size="sm"
        className="text-slate-400 hover:text-red-400"
      >
        <LogOut className="w-4 h-4 mr-2" />
        Logout
      </Button>
    </header>
  );
}
