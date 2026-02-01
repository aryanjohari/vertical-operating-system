"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAppStore } from "@/store/useAppStore";
import { Menu, LogOut } from "lucide-react";

function Breadcrumbs() {
  const pathname = usePathname();
  const currentProjectId = useAppStore((s) => s.currentProjectId);
  const projectIdFromPath = pathname.match(/^\/projects\/([^/]+)/)?.[1] ?? null;
  const projectId = currentProjectId ?? projectIdFromPath;

  const segments: { label: string; href?: string }[] = [{ label: "Projects", href: "/projects" }];

  if (projectId) {
    const nicheSlug = projectId.replace(/_/g, " ");
    const nicheLabel = nicheSlug.charAt(0).toUpperCase() + nicheSlug.slice(1);
    segments.push({ label: nicheLabel, href: `/projects/${projectId}` });

    const routeMap: Record<string, string> = {
      intel: "Intel",
      strategy: "Strategy",
      quality: "Quality",
      leads: "Leads",
      settings: "Settings",
    };
    const pathParts = pathname.split("/").filter(Boolean);
    const lastPart = pathParts[pathParts.length - 1];
    if (lastPart && lastPart !== projectId && routeMap[lastPart]) {
      segments.push({ label: routeMap[lastPart] });
    }
  }

  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      {segments.map((seg, i) => (
        <span key={i} className="flex items-center gap-2">
          {i > 0 && <span>/</span>}
          {seg.href ? (
            <Link href={seg.href} className="hover:text-foreground">
              {seg.label}
            </Link>
          ) : (
            <span className="text-foreground">{seg.label}</span>
          )}
        </span>
      ))}
    </div>
  );
}

export function Topbar() {
  const pathname = usePathname();
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
        <Breadcrumbs />
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">{user?.id}</span>
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
