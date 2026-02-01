"use client";

import React from "react";
import { cn } from "@/lib/utils";
import Card from "@/components/ui/Card";

interface MetricCardProps {
  title: string;
  value: string | number;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export default function MetricCard({
  title,
  value,
  trend,
  className,
}: MetricCardProps) {
  return (
    <Card className={cn("p-4", className)}>
      <p className="text-sm font-medium text-muted-foreground">{title}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
      {trend !== undefined && trend !== "neutral" && (
        <p
          className={cn(
            "mt-1 text-xs",
            trend === "up" && "text-emerald-500",
            trend === "down" && "text-red-500"
          )}
        >
          {trend === "up" ? "↑" : "↓"} vs last period
        </p>
      )}
    </Card>
  );
}
