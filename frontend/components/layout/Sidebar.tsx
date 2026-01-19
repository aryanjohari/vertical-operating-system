"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { LayoutDashboard, Database, Terminal, Users } from "lucide-react";

const navItems = [
  { name: "Mission Control", href: "/dashboard", icon: LayoutDashboard },
  { name: "Asset Database", href: "/dashboard/assets", icon: Database },
  { name: "Agent Console", href: "/dashboard/console", icon: Terminal },
  { name: "Leads", href: "/dashboard/leads", icon: Users },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="w-64 border-r border-purple-500/20 bg-slate-950/50 p-4">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-purple-400 flex items-center gap-2">
          <span className="text-2xl">⚡</span> Apex Sovereign OS
        </h1>
      </div>
      <nav className="space-y-2">
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
