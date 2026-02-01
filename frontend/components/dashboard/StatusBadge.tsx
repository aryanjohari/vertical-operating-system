"use client";

import React from "react";
import { cn } from "@/lib/utils";

type Status = "active" | "error" | "draft" | "pending";

interface StatusBadgeProps {
  status: Status;
  className?: string;
  children?: React.ReactNode;
}

const statusConfig: Record<
  Status,
  { label: string; className: string; pulse?: boolean }
> = {
  active: {
    label: "Active",
    className: "text-emerald-500 border-emerald-500/30 bg-emerald-500/10",
    pulse: true,
  },
  error: {
    label: "Error",
    className: "text-red-500 border-red-500/30 bg-red-500/10",
  },
  draft: {
    label: "Draft",
    className: "text-muted-foreground border-border bg-muted/50",
  },
  pending: {
    label: "Pending",
    className: "text-amber-500 border-amber-500/30 bg-amber-500/10",
  },
};

export default function StatusBadge({
  status,
  className,
  children,
}: StatusBadgeProps) {
  const config = statusConfig[status] ?? statusConfig.draft;
  const label = children ?? config.label;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        config.className,
        config.pulse && "animate-pulse",
        className
      )}
    >
      {config.pulse && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full rounded-full bg-current opacity-75 animate-ping" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
        </span>
      )}
      {label}
    </span>
  );
}
