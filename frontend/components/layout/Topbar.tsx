"use client";

import { useAppStore } from "@/store/useAppStore";
import { Menu, LogOut } from "lucide-react";

function UserAvatar({ email }: { email: string }) {
  const initial = email.charAt(0).toUpperCase();
  return (
    <div
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/20 text-sm font-medium text-primary"
      aria-hidden
    >
      {initial}
    </div>
  );
}

export function Topbar() {
  const user = useAppStore((s) => s.user);
  const logout = useAppStore((s) => s.logout);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-background/80 px-4 backdrop-blur-sm">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={toggleSidebar}
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Toggle sidebar"
        >
          <Menu className="h-5 w-5" />
        </button>
        <h1 className="acid-text text-lg font-semibold text-foreground">
          Apex OS Control Panel
        </h1>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          {user?.id && <UserAvatar email={user.id} />}
          <span className="text-sm text-muted-foreground" title="User Profile">
            {user?.id}
          </span>
        </div>
        <button
          type="button"
          onClick={logout}
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Log out"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
