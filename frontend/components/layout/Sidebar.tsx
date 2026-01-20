"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { LayoutDashboard, Database, Users, Plus, Settings } from "lucide-react";
import { useProjects } from "@/hooks/useProjects";
import { useProjectContext } from "@/hooks/useProjectContext";
import { Button } from "@/components/ui/button";

const navItems = [
  { name: "Mission Control", href: "/dashboard", icon: LayoutDashboard },
  { name: "Content Library", href: "/dashboard/assets", icon: Database },
  { name: "Leads", href: "/dashboard/leads", icon: Users },
  { name: "Settings", href: "/dashboard/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { projects, isLoading: projectsLoading, mutate: refreshProjects } = useProjects();
  const { projectId, setProjectId } = useProjectContext();

  const handleNewProject = () => {
    router.push("/onboarding");
  };

  return (
    <div className="w-64 border-r border-purple-500/20 bg-slate-950/50 p-4 flex flex-col">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-purple-400 flex items-center gap-2">
          <span className="text-2xl">⚡</span> Apex Sovereign OS
        </h1>
      </div>

      {/* Project Selector */}
      <div className="mb-6">
        <label className="text-xs text-slate-500 mb-2 block">Project</label>
        <select
          value={projectId || ""}
          onChange={(e) => setProjectId(e.target.value || null)}
          className="w-full bg-slate-900 border border-purple-500/30 rounded-md px-3 py-2 text-sm text-purple-300 focus:outline-none focus:ring-2 focus:ring-purple-500/50"
          disabled={projectsLoading}
        >
          <option value="">Select a project...</option>
          {projects.map((project) => (
            <option key={project.project_id} value={project.project_id}>
              {project.niche || project.project_id}
            </option>
          ))}
        </select>

        {/* New Project Button */}
        <Button
          onClick={handleNewProject}
          variant="outline"
          size="sm"
          className="w-full mt-2 border-purple-500/30 text-purple-300 hover:bg-purple-500/10"
        >
          <Plus className="w-4 h-4 mr-2" />
          New Project
        </Button>
      </div>

      {/* Navigation */}
      <nav className="space-y-2 flex-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-4 py-2 rounded-md transition-colors",
                isActive
                  ? "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                  : "text-slate-400 hover:bg-slate-900 hover:text-purple-300"
              )}
            >
              <Icon className="w-5 h-5" />
              <span className="text-sm font-medium">{item.name}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
