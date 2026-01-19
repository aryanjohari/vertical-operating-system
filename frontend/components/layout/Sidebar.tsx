"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { LayoutDashboard, Database, Terminal, Users, Plus } from "lucide-react";
import { useProjects } from "@/hooks/useProjects";
import { useProjectContext } from "@/hooks/useProjectContext";
import { Button } from "@/components/ui/button";

const navItems = [
  { name: "Mission Control", href: "/dashboard", icon: LayoutDashboard },
  { name: "Asset Database", href: "/dashboard/assets", icon: Database },
  { name: "Agent Console", href: "/dashboard/console", icon: Terminal },
  { name: "Leads", href: "/dashboard/leads", icon: Users },
];

export function Sidebar() {
  const pathname = usePathname();
  const { projects, isLoading: projectsLoading, createProject } = useProjects();
  const { projectId, setProjectId } = useProjectContext();
  const [showNewProjectForm, setShowNewProjectForm] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectNiche, setNewProjectNiche] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const currentProject = projects.find((p) => p.project_id === projectId);

  const handleCreateProject = async () => {
    if (!newProjectName.trim() || !newProjectNiche.trim()) {
      return;
    }
    setIsCreating(true);
    try {
      const result = await createProject(newProjectName, newProjectNiche);
      setProjectId(result.project_id);
      setShowNewProjectForm(false);
      setNewProjectName("");
      setNewProjectNiche("");
    } catch (error) {
      console.error("Failed to create project:", error);
    } finally {
      setIsCreating(false);
    }
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
          onClick={() => setShowNewProjectForm(!showNewProjectForm)}
          variant="outline"
          size="sm"
          className="w-full mt-2 border-purple-500/30 text-purple-300 hover:bg-purple-500/10"
        >
          <Plus className="w-4 h-4 mr-2" />
          New Project
        </Button>

        {/* New Project Form */}
        {showNewProjectForm && (
          <div className="mt-3 p-3 bg-slate-900/50 border border-purple-500/20 rounded-md space-y-2">
            <input
              type="text"
              placeholder="Project Name"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              className="w-full bg-slate-800 border border-purple-500/20 rounded px-2 py-1 text-sm text-purple-300 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-purple-500/50"
            />
            <input
              type="text"
              placeholder="Niche (e.g., bail-v1)"
              value={newProjectNiche}
              onChange={(e) => setNewProjectNiche(e.target.value)}
              className="w-full bg-slate-800 border border-purple-500/20 rounded px-2 py-1 text-sm text-purple-300 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-purple-500/50"
            />
            <div className="flex gap-2">
              <Button
                onClick={handleCreateProject}
                disabled={isCreating || !newProjectName.trim() || !newProjectNiche.trim()}
                size="sm"
                className="flex-1 bg-purple-600 hover:bg-purple-700"
              >
                {isCreating ? "Creating..." : "Create"}
              </Button>
              <Button
                onClick={() => {
                  setShowNewProjectForm(false);
                  setNewProjectName("");
                  setNewProjectNiche("");
                }}
                variant="ghost"
                size="sm"
                className="flex-1"
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
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
