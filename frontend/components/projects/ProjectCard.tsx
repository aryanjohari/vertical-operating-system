import Link from "next/link";
import type { Project } from "@/types";
import { cn } from "@/lib/utils";

interface ProjectCardProps {
  project: Project;
  leadCount?: number;
}

function StatusBadge({ status }: { status: "active" | "draft" }) {
  return (
    <span
      className={cn(
        "inline-flex rounded px-2 py-0.5 text-xs font-medium",
        status === "active"
          ? "bg-primary/20 text-primary"
          : "bg-muted text-muted-foreground"
      )}
    >
      {status === "active" ? "Active" : "Draft"}
    </span>
  );
}

export function ProjectCard({ project, leadCount = 0 }: ProjectCardProps) {
  const name = project.niche || project.project_id;
  const displayName =
    name.charAt(0).toUpperCase() + name.replace(/_/g, " ").slice(1);

  return (
    <Link href={`/projects/${project.project_id}`}>
      <div className="glass-panel group flex flex-col gap-3 p-6 transition-all hover:border-primary/40 hover:shadow-[0_0_20px_2px_hsl(0_100%_60%/0.08)]">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors">
            {displayName}
          </h3>
          <StatusBadge status="active" />
        </div>
        <p className="text-sm text-muted-foreground truncate">
          {project.project_id}
        </p>
        <div className="mt-auto flex items-center gap-4 text-sm">
          <span className="text-muted-foreground">
            <span className="font-medium text-foreground">{leadCount}</span> leads
          </span>
        </div>
      </div>
    </Link>
  );
}
