"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { createProjectWithProfile } from "@/lib/api";
import { DynamicForm } from "@/components/forms/DynamicForm";
import { toast } from "sonner";

interface CreateProjectDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function CreateProjectDialog({
  isOpen,
  onClose,
  onSuccess,
}: CreateProjectDialogProps) {
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (payload: Record<string, unknown>) => {
    setLoading(true);
    try {
      const result = await createProjectWithProfile(payload);
      if (result.success) {
        toast.success("Project created successfully.", {
          style: { background: "hsl(180 100% 50% / 0.1)", borderColor: "hsl(180 100% 50%)" },
        });
        onClose();
        onSuccess();
      } else {
        toast.error("Failed to create project.", {
          style: { background: "hsl(0 100% 60% / 0.2)", borderColor: "hsl(0 100% 60%)" },
        });
      }
    } catch {
      toast.error("Failed to create project. Please try again.", {
        style: { background: "hsl(0 100% 60% / 0.2)", borderColor: "hsl(0 100% 60%)" },
      });
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={handleClose}
        aria-hidden
      />
      <div className="glass-panel acid-glow relative z-10 flex max-h-[90vh] w-full max-w-2xl flex-col border border-primary/30">
        <div className="flex shrink-0 items-center justify-between border-b border-border p-4">
          <h2 className="acid-text text-lg font-semibold text-foreground">
            Create New Project
          </h2>
          <button
            type="button"
            onClick={handleClose}
            disabled={loading}
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-60"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4">
            <DynamicForm
              schemaType="profile"
              onSubmit={handleSubmit}
              submitLabel="Create Project"
              loading={loading}
              onCancel={handleClose}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
