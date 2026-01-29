"use client";

import React from "react";

interface ShellProps {
  children: React.ReactNode;
}

export default function Shell({ children }: ShellProps) {
  return (
    <div
      className="min-h-screen flex flex-col"
      style={{
        background: "var(--bg-terminal)",
        color: "var(--fg-primary, #00ff9d)",
      }}
    >
      <header
        className="flex items-center h-12 border-b shrink-0"
        style={{ borderColor: "var(--border-dim)" }}
      >
        <span className="px-4 font-mono text-sm">Apex Sovereign OS</span>
      </header>
      <div className="flex flex-1 min-h-0">
        <aside
          className="w-48 border-r shrink-0"
          style={{ borderColor: "var(--border-dim)" }}
        >
          <nav className="p-2 font-mono text-sm">
            <div className="py-1 px-2 opacity-70">Dashboard</div>
            <div className="py-1 px-2 opacity-70">Projects</div>
            <div className="py-1 px-2 opacity-70">System</div>
          </nav>
        </aside>
        <main
          className="flex-1 overflow-auto p-4"
          style={{
            background: "var(--bg-terminal)",
            color: "#e5e5e5",
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
