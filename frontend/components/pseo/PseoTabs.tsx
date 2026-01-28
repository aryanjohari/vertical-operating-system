"use client";

import { useRouter } from "next/navigation";

interface PseoTabsProps {
  projectId: string;
  campaignId: string;
  current: "pulse" | "intel" | "strategy" | "quality";
}

const TABS: { id: "pulse" | "intel" | "strategy" | "quality"; label: string }[] = [
  { id: "pulse", label: "Pulse" },
  { id: "intel", label: "Intel" },
  { id: "strategy", label: "Strategy" },
  { id: "quality", label: "Quality" },
];

export default function PseoTabs({
  projectId,
  campaignId,
  current,
}: PseoTabsProps) {
  const router = useRouter();
  const base = `/projects/${projectId}`;
  const q = new URLSearchParams({ campaign: campaignId });

  const go = (id: "pulse" | "intel" | "strategy" | "quality") => {
    if (id === "pulse") {
      router.push(`${base}?${q.toString()}`);
      return;
    }
    router.push(`${base}/pseo/${id}?${q.toString()}`);
  };

  return (
    <div className="mb-6 flex gap-1 rounded-lg border border-gray-200 bg-gray-100/50 p-1 dark:border-gray-700 dark:bg-gray-800/50">
      {TABS.map((tab) => {
        const active = current === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => go(tab.id)}
            className={`rounded-md px-4 py-2 text-sm font-medium transition ${
              active
                ? "bg-white text-gray-900 shadow dark:bg-gray-800 dark:text-white"
                : "text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
            }`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
