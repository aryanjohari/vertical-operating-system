"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface AddKeywordsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (keywords: string[]) => Promise<void>;
}

export function AddKeywordsModal({
  isOpen,
  onClose,
  onSubmit,
}: AddKeywordsModalProps) {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const keywords = value
      .split(/[\n,]+/)
      .map((k) => k.trim().toLowerCase())
      .filter(Boolean);
    if (keywords.length === 0) return;
    setLoading(true);
    try {
      await onSubmit(keywords);
      setValue("");
      onClose();
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <div className="glass-panel acid-glow relative z-10 w-full max-w-lg border border-primary/30 p-6">
        <div className="flex items-center justify-between">
          <h2 className="acid-text text-lg font-semibold text-foreground">
            Add Keywords
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label
              htmlFor="keywords"
              className="block text-sm font-medium text-foreground"
            >
              Paste keywords (one per line or comma-separated)
            </label>
            <textarea
              id="keywords"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="plumber auckland&#10;emergency plumbing&#10;water heater repair"
              rows={6}
              disabled={loading}
              className={cn(
                "mt-1 w-full rounded border border-border bg-muted/50 px-3 py-2 font-mono text-sm text-foreground placeholder:text-muted-foreground",
                "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background",
                "disabled:cursor-not-allowed disabled:opacity-60"
              )}
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !value.trim()}
              className="acid-glow rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Adding..." : "Add Keywords"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
