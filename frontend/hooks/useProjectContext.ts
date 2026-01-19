"use client";

import { useState, useEffect } from "react";

const PROJECT_CONTEXT_KEY = "apex_current_project_id";

export function useProjectContext() {
  const [projectId, setProjectIdState] = useState<string | null>(null);

  useEffect(() => {
    // Load from localStorage on mount
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(PROJECT_CONTEXT_KEY);
      if (stored) {
        setProjectIdState(stored);
      }
    }
  }, []);

  const setProjectId = (id: string | null) => {
    setProjectIdState(id);
    if (typeof window !== "undefined") {
      if (id) {
        localStorage.setItem(PROJECT_CONTEXT_KEY, id);
      } else {
        localStorage.removeItem(PROJECT_CONTEXT_KEY);
      }
    }
  };

  return {
    projectId,
    setProjectId,
  };
}
