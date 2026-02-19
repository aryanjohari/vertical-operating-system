"use client";

import { useState, useEffect } from "react";
import { X, Check, XCircle } from "lucide-react";
import type { PageDraft } from "@/types";
import { cn } from "@/lib/utils";

interface PreviewModalProps {
  draft: PageDraft;
  isOpen: boolean;
  onClose: () => void;
  onApprove: (draft: PageDraft) => Promise<void>;
  onReject: (draft: PageDraft) => Promise<void>;
}

export function PreviewModal({
  draft,
  isOpen,
  onClose,
  onApprove,
  onReject,
}: PreviewModalProps) {
  const [title, setTitle] = useState(String(draft.metadata?.title ?? draft.name ?? ""));
  const [slug, setSlug] = useState(String((draft.metadata?.slug as string) ?? ""));
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setTitle(String(draft.metadata?.title ?? draft.name ?? ""));
    setSlug(String((draft.metadata?.slug as string) ?? ""));
  }, [draft.id, draft.metadata?.title, draft.metadata?.slug, draft.name]);

  if (!isOpen) return null;

  const content = (draft.metadata?.content as string) ?? "";
  const handleApprove = async () => {
    setLoading(true);
    try {
      await onApprove({ ...draft, metadata: { ...draft.metadata, title, slug } });
      onClose();
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    setLoading(true);
    try {
      await onReject(draft);
      onClose();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <div className="glass-panel acid-glow relative z-10 flex h-[85vh] max-h-[800px] w-full max-w-5xl flex-col overflow-hidden border border-primary/30">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="acid-text text-lg font-semibold text-foreground">
            {draft.name || "Page Draft"}
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
        <div className="flex min-h-0 flex-1">
          {/* Left: Rendered HTML */}
          <div className="flex-1 overflow-auto border-r border-border bg-muted/30 p-4">
            <div
              className="max-w-none rounded border border-border bg-background/50 p-6 [&_h1]:text-xl [&_h2]:text-lg [&_p]:my-2 [&_ul]:list-inside [&_ul]:list-disc"
              dangerouslySetInnerHTML={{
                __html:
                  content ||
                  '<p class="text-muted-foreground">No content</p>',
              }}
            />
          </div>
          {/* Right: Metadata Form */}
          <div className="w-80 shrink-0 overflow-auto p-4">
            <div className="space-y-4">
              <div>
                <label
                  htmlFor="preview-title"
                  className="block text-sm font-medium text-foreground"
                >
                  Title
                </label>
                <input
                  id="preview-title"
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  disabled={loading}
                  className={cn(
                    "mt-1 w-full rounded border border-border bg-muted/50 px-3 py-2 text-foreground",
                    "focus:outline-none focus:ring-2 focus:ring-primary",
                    "disabled:opacity-60"
                  )}
                />
              </div>
              <div>
                <label
                  htmlFor="preview-slug"
                  className="block text-sm font-medium text-foreground"
                >
                  Slug
                </label>
                <input
                  id="preview-slug"
                  type="text"
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                  placeholder="/page-slug"
                  disabled={loading}
                  className={cn(
                    "mt-1 w-full rounded border border-border bg-muted/50 px-3 py-2 text-foreground",
                    "focus:outline-none focus:ring-2 focus:ring-primary",
                    "disabled:opacity-60"
                  )}
                />
              </div>
              <div className="flex gap-2 pt-4">
                <button
                  type="button"
                  onClick={handleApprove}
                  disabled={loading}
                  className="acid-glow flex flex-1 items-center justify-center gap-2 rounded bg-primary py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
                >
                  <Check className="h-4 w-4" />
                  Approve
                </button>
                <button
                  type="button"
                  onClick={handleReject}
                  disabled={loading}
                  className="flex flex-1 items-center justify-center gap-2 rounded border border-primary/50 bg-primary/10 py-2 text-sm font-medium text-primary hover:bg-primary/20 disabled:opacity-60"
                >
                  <XCircle className="h-4 w-4" />
                  Reject
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
