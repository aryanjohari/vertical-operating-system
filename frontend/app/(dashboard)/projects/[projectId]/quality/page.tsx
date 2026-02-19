"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getEntities, updateEntity } from "@/lib/api";
import type { PageDraft } from "@/types";
import { PreviewModal } from "@/components/drafts/PreviewModal";

const DRAFTING_STATUSES = ["processing", "drafted", "draft"];
const REVIEW_STATUSES = [
  "in_review",
  "needs_revision",
  "validated",
  "ready_for_media",
  "ready_for_utility",
  "rejected",
];
const READY_STATUSES = ["ready_to_publish", "approved", "published", "live"];

function KanbanColumn({
  title,
  drafts,
  onCardClick,
}: {
  title: string;
  drafts: PageDraft[];
  onCardClick: (draft: PageDraft) => void;
}) {
  return (
    <div className="flex min-w-[280px] flex-1 flex-col">
      <h3 className="mb-3 text-sm font-medium text-muted-foreground">{title}</h3>
      <div className="flex flex-1 flex-col gap-2 overflow-y-auto rounded border border-border bg-muted/20 p-3">
        {drafts.map((draft) => (
          <button
            key={draft.id}
            type="button"
            onClick={() => onCardClick(draft)}
            className="glass-panel group rounded border border-border p-4 text-left transition-all hover:border-primary/40 hover:shadow-[0_0_12px_2px_hsl(0_100%_60%/0.06)]"
          >
            <p className="font-medium text-foreground line-clamp-1">
              {String(draft.metadata?.title ?? draft.name ?? "Untitled")}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {String((draft.metadata?.status as string) ?? "—")}
            </p>
          </button>
        ))}
        {drafts.length === 0 && (
          <div className="py-8 text-center text-sm text-muted-foreground">
            No drafts
          </div>
        )}
      </div>
    </div>
  );
}

function ColumnSkeleton() {
  return (
    <div className="flex min-w-[280px] flex-1 flex-col">
      <div className="mb-3 h-4 w-24 animate-pulse rounded bg-muted" />
      <div className="flex flex-1 flex-col gap-2 rounded border border-border bg-muted/20 p-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-20 animate-pulse rounded border border-border bg-muted/50"
          />
        ))}
      </div>
    </div>
  );
}

export default function QualityPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  const [drafts, setDrafts] = useState<PageDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [previewDraft, setPreviewDraft] = useState<PageDraft | null>(null);

  const loadDrafts = useCallback(async () => {
    const data = await getEntities<PageDraft>("page_draft", projectId);
    setDrafts(data);
  }, [projectId]);

  useEffect(() => {
    queueMicrotask(() => {
      loadDrafts()
        .catch(() => setDrafts([]))
        .finally(() => setLoading(false));
    });
  }, [loadDrafts]);

  const drafting = drafts.filter((d) =>
    DRAFTING_STATUSES.includes((d.metadata?.status as string) ?? "")
  );
  const review = drafts.filter((d) => {
    const s = (d.metadata?.status as string) ?? "";
    return (
      REVIEW_STATUSES.includes(s) ||
      (!DRAFTING_STATUSES.includes(s) && !READY_STATUSES.includes(s))
    );
  });
  const ready = drafts.filter((d) =>
    READY_STATUSES.includes((d.metadata?.status as string) ?? "")
  );

  const handleApprove = async (draft: PageDraft) => {
    await updateEntity(draft.id, {
      ...draft.metadata,
      status: "approved",
    });
    await loadDrafts();
  };

  const handleReject = async (draft: PageDraft) => {
    await updateEntity(draft.id, {
      ...draft.metadata,
      status: "needs_revision",
    });
    await loadDrafts();
  };

  return (
    <div className="space-y-6">
      <h1 className="acid-text text-2xl font-bold text-foreground">
        Page Drafts
      </h1>

      {loading ? (
        <div className="flex gap-4">
          <ColumnSkeleton />
          <ColumnSkeleton />
          <ColumnSkeleton />
        </div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-4">
          <KanbanColumn
            title="Drafting"
            drafts={drafting}
            onCardClick={setPreviewDraft}
          />
          <KanbanColumn
            title="Review"
            drafts={review}
            onCardClick={setPreviewDraft}
          />
          <KanbanColumn
            title="Ready"
            drafts={ready}
            onCardClick={setPreviewDraft}
          />
        </div>
      )}

      {previewDraft && (
        <PreviewModal
          draft={previewDraft}
          isOpen={!!previewDraft}
          onClose={() => setPreviewDraft(null)}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      )}
    </div>
  );
}
