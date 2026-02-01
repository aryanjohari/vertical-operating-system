"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/store/useAppStore";

export function RedirectHome() {
  const router = useRouter();
  const token = useAppStore((s) => s.token);
  const _hydrated = useAppStore((s) => s._hydrated);

  useEffect(() => {
    if (!_hydrated) return;
    if (token) {
      router.replace("/projects");
    } else {
      router.replace("/login");
    }
  }, [token, _hydrated, router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-muted-foreground">Loading...</p>
    </div>
  );
}
