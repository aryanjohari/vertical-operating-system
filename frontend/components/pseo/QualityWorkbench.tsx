"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { Entity } from "@/lib/types";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Modal from "@/components/ui/Modal";

interface QualityWorkbenchProps {
  projectId: string;
  campaignId: string;
}

export default function QualityWorkbench({
  projectId,
  campaignId,
}: QualityWorkbenchProps) {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<"all" | "draft" | "rejected">(
    "all",
  );
  const [activeDraft, setActiveDraft] = useState<Entity | null>(null);
  const [editorValue, setEditorValue] = useState<string>("");

  const { data: entities, isLoading } = useQuery({
    queryKey: ["entities", projectId, "page_draft"],
    queryFn: async () => {
      const response = await api.get("/api/entities", {
        params: {
          project_id: projectId,
          entity_type: "page_draft",
        },
      });
      const all: Entity[] = response.data.entities || [];
      return all.filter(
        (e) =>
          e.metadata?.campaign_id === campaignId &&
          ["draft", "rejected"].includes(e.metadata?.status || ""),
      );
    },
  });

  const drafts = entities || [];

  const filteredDrafts = drafts.filter((d) => {
    if (statusFilter === "all") return true;
    return d.metadata?.status === statusFilter;
  });

  const mutation = useMutation({
    mutationFn: async () => {
      if (!activeDraft) return;
      await api.post("/api/run", {
        task: "manager",
        user_id: "",
        params: {
          project_id: projectId,
          campaign_id: campaignId,
          action: "force_approve_draft",
          draft_id: activeDraft.id,
          content: editorValue,
        },
      });
    },
    onSuccess: async () => {
      setActiveDraft(null);
      await queryClient.invalidateQueries({
        queryKey: ["entities", projectId, "page_draft"],
      });
    },
  });

  const openEditor = (draft: Entity) => {
    const meta = draft.metadata || {};
    const content = meta.content || meta.html_content || "";
    setActiveDraft(draft);
    setEditorValue(content);
  };

  const closeEditor = () => {
    if (mutation.isPending) return;
    setActiveDraft(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Quality Gate
          </h2>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Review and fix drafts before they pass Critic. Focus on rejected or unreviewed pages.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) =>
              setStatusFilter(e.target.value as "all" | "draft" | "rejected")
            }
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
          >
            <option value="all">All (draft + rejected)</option>
            <option value="draft">Unreviewed only</option>
            <option value="rejected">Rejected only</option>
          </select>
        </div>
      </div>

      {isLoading && (
        <Card className="p-6 text-sm text-gray-600 dark:text-gray-400">
          Loading drafts...
        </Card>
      )}

      {!isLoading && drafts.length === 0 && (
        <Card className="p-6 text-sm text-gray-600 dark:text-gray-400">
          No drafts waiting for review. Run Writer to create drafts.
        </Card>
      )}

      {!isLoading && drafts.length > 0 && (
        <Card className="p-0 overflow-hidden">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500 dark:border-gray-800 dark:text-gray-400">
                <th className="px-4 py-2">Title</th>
                <th className="px-4 py-2 hidden md:table-cell">Keyword</th>
                <th className="px-4 py-2 hidden md:table-cell">Status</th>
                <th className="px-4 py-2 hidden md:table-cell">QA Score</th>
                <th className="px-4 py-2 hidden md:table-cell">Notes</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {filteredDrafts.map((draft) => {
                const meta = draft.metadata || {};
                const status = meta.status || "draft";
                const score = meta.qa_score ?? "-";
                const notes = meta.qa_notes || "";

                return (
                  <tr
                    key={draft.id}
                    className="border-b border-gray-100 text-xs last:border-b-0 dark:border-gray-800"
                  >
                    <td className="px-4 py-2 text-gray-900 dark:text-white">
                      {draft.name}
                    </td>
                    <td className="px-4 py-2 text-gray-600 dark:text-gray-400 hidden md:table-cell">
                      {meta.keyword || "-"}
                    </td>
                    <td className="px-4 py-2 hidden md:table-cell">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${
                          status === "rejected"
                            ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                            : "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200"
                        }`}
                      >
                        {status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-600 dark:text-gray-400 hidden md:table-cell">
                      {score}
                    </td>
                    <td className="px-4 py-2 text-gray-600 dark:text-gray-400 hidden md:table-cell">
                      {notes ? String(notes).slice(0, 80) : "-"}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => openEditor(draft)}
                      >
                        Review
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}

      <Modal
        isOpen={!!activeDraft}
        onClose={closeEditor}
        title={
          activeDraft
            ? `Quality Review: ${activeDraft.metadata?.keyword || activeDraft.name}`
            : "Quality Review"
        }
      >
        {activeDraft && (
          <div className="space-y-4">
            <div className="space-y-1 text-xs text-gray-500 dark:text-gray-400">
              <p>
                Status:{" "}
                <span className="font-semibold text-gray-900 dark:text-white">
                  {activeDraft.metadata?.status || "draft"}
                </span>
              </p>
              {activeDraft.metadata?.qa_notes && (
                <p>Notes: {String(activeDraft.metadata.qa_notes)}</p>
              )}
            </div>

            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Content
            </label>
            <textarea
              className="h-64 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              value={editorValue}
              onChange={(e) => setEditorValue(e.target.value)}
            />

            <div className="flex items-center justify-end gap-3 pt-2">
              <Button
                variant="secondary"
                onClick={closeEditor}
                disabled={mutation.isPending}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={() => mutation.mutate()}
                isLoading={mutation.isPending}
              >
                Force Approve
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

