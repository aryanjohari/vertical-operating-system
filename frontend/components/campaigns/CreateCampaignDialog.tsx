"use client";

import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { createCampaignWithForm } from "@/lib/api";
import { cn } from "@/lib/utils";
import { DynamicForm } from "@/components/forms/DynamicForm";
import { toast } from "sonner";

const inputClass = cn(
  "w-full rounded border border-border bg-muted/50 px-3 py-2 text-foreground placeholder:text-muted-foreground",
  "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background",
  "disabled:cursor-not-allowed disabled:opacity-60"
);

interface CreateCampaignDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  projectId: string;
  module: "pseo" | "lead_gen";
}

export function CreateCampaignDialog({
  isOpen,
  onClose,
  onSuccess,
  projectId,
  module,
}: CreateCampaignDialogProps) {
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState("");

  useEffect(() => {
    if (isOpen) setName("");
  }, [isOpen]);

  const handleSubmit = async (payload: Record<string, unknown>) => {
    setLoading(true);
    try {
      await createCampaignWithForm(projectId, module, payload, name || undefined);
      toast.success("Campaign created successfully.", {
        style: { background: "hsl(180 100% 50% / 0.1)", borderColor: "hsl(180 100% 50%)" },
      });
      setName("");
      onClose();
      onSuccess();
    } catch {
      toast.error("Failed to create campaign. Please try again.", {
        style: { background: "hsl(0 100% 60% / 0.2)", borderColor: "hsl(0 100% 60%)" },
      });
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const title = module === "pseo" ? "Create pSEO Campaign" : "Create Lead Gen Campaign";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <div className="glass-panel acid-glow relative z-10 flex max-h-[90vh] w-full max-w-2xl flex-col border border-primary/30">
        <div className="flex shrink-0 items-center justify-between border-b border-border p-4">
          <h2 className="acid-text text-lg font-semibold text-foreground">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-60"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div>
              <label className="block text-xs font-medium text-muted-foreground">
                Campaign Name (optional)
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={module === "pseo" ? "Emergency Bail - Auckland" : "Lead Gen Campaign"}
                disabled={loading}
                className={cn(inputClass, "mt-1")}
              />
            </div>
            <DynamicForm
              schemaType={module}
              onSubmit={handleSubmit}
              submitLabel="Create Campaign"
              loading={loading}
              onCancel={onClose}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
