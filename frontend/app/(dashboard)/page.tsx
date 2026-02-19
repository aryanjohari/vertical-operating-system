"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Dashboard root: redirect to Analytics.
 */
export default function DashboardRootPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/analytics");
  }, [router]);
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <p className="text-muted-foreground">Redirecting to Analytics…</p>
    </div>
  );
}
