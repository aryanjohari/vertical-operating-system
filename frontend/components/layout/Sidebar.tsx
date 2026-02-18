"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAppStore } from "@/store/useAppStore";
import { FolderOpen, Settings, Users, Rocket } from "lucide-react";

const projectNavItems = [
  { href: (id: string) => `/projects/${id}`, label: "pSEO", icon: Rocket },
  { href: (id: string) => `/projects/${id}/leads`, label: "Lead Gen", icon: Users },
  { href: (id: string) => `/projects/${id}/settings`, label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const currentProjectId = useAppStore((s) => s.currentProjectId);
  const isSidebarOpen = useAppStore((s) => s.isSidebarOpen);
  const setProject = useAppStore((s) => s.setProject);

  const projectIdFromPath = pathname.match(/^\/projects\/([^/]+)/)?.[1] ?? null;
  const effectiveProjectId = currentProjectId ?? projectIdFromPath;

  useEffect(() => {
    if (projectIdFromPath) setProject(projectIdFromPath);
    else if (pathname === "/projects") setProject(null);
  }, [pathname, projectIdFromPath, setProject]);

  if (!isSidebarOpen) return null;

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 glass-panel border-r border-border">
      <nav className="flex flex-col gap-1 p-4">
        <Link
          href="/projects"
          onClick={() => setProject(null)}
          className={`flex items-center gap-2 rounded px-3 py-2 text-sm font-medium transition-colors ${
            pathname === "/projects"
              ? "bg-primary/20 text-primary"
              : "text-foreground hover:bg-muted"
          }`}
        >
          <FolderOpen className="h-4 w-4" />
          All Projects
        </Link>

        {effectiveProjectId && (
          <>
            <div className="my-2 h-px bg-border" />
            {projectNavItems.map(({ href, label, icon: Icon }) => {
              const targetHref = href(effectiveProjectId);
              const isActive = pathname === targetHref || pathname.startsWith(targetHref + "/");
              return (
                <Link
                  key={targetHref}
                  href={targetHref}
                  onClick={() => setProject(effectiveProjectId)}
                  className={`flex items-center gap-2 rounded px-3 py-2 text-sm font-medium transition-colors ${
                    isActive ? "bg-primary/20 text-primary" : "text-foreground hover:bg-muted"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </Link>
              );
            })}
          </>
        )}
      </nav>
    </aside>
  );
}
