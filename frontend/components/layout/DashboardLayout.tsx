"use client";

import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { useAppStore } from "@/store/useAppStore";

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  const isSidebarOpen = useAppStore((s) => s.isSidebarOpen);
  return (
    <div className="min-h-screen">
      <Sidebar />
      <div className={isSidebarOpen ? "pl-64" : ""}>
        <Topbar />
        <main className="p-4">{children}</main>
      </div>
    </div>
  );
}
