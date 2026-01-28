"use client";

import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { Entity } from "@/lib/types";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

interface IntelWorkbenchProps {
  projectId: string;
  campaignId: string;
}

export default function IntelWorkbench({
  projectId,
  campaignId,
}: IntelWorkbenchProps) {
  const queryClient = useQueryClient();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [operation, setOperation] = useState<"exclude" | "delete">("exclude");

  const { data: entities, isLoading } = useQuery({
    queryKey: ["entities", projectId, "anchor_location"],
    queryFn: async () => {
      const response = await api.get("/api/entities", {
        params: {
          project_id: projectId,
          entity_type: "anchor_location",
        },
      });
      const all: Entity[] = response.data.entities || [];
      return all.filter(
        (e) =>
          e.metadata?.campaign_id === campaignId &&
          !e.metadata?.excluded,
      );
    },
  });

  const anchors = entities || [];

  const mutation = useMutation({
    mutationFn: async () => {
      if (selectedIds.size === 0) return;
      await api.post("/api/run", {
        task: "manager",
        user_id: "",
        params: {
          project_id: projectId,
          campaign_id: campaignId,
          action: "intel_review",
          ids: Array.from(selectedIds),
          operation,
        },
      });
    },
    onSuccess: async () => {
      setSelectedIds(new Set());
      await queryClient.invalidateQueries({
        queryKey: ["entities", projectId, "anchor_location"],
      });
    },
  });

  const allSelected = useMemo(
    () => anchors.length > 0 && selectedIds.size === anchors.length,
    [anchors.length, selectedIds],
  );

  const toggleAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(anchors.map((a) => a.id)));
    }
  };

  const toggleOne = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Intel Review
          </h2>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Bulk-review anchors from Scout. Exclude irrelevant locations before Strategist runs.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={operation}
            onChange={(e) =>
              setOperation(e.target.value as "exclude" | "delete")
            }
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
          >
            <option value="exclude">Exclude from pipeline</option>
            <option value="delete">Delete permanently</option>
          </select>
          <Button
            size="sm"
            variant="primary"
            disabled={selectedIds.size === 0 || mutation.isPending}
            isLoading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {operation === "delete" ? "Delete Selected" : "Exclude Selected"}
          </Button>
        </div>
      </div>

      <Card className="p-0 overflow-hidden">
        <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-3 text-xs font-medium uppercase tracking-wide text-gray-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400">
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
              className="h-4 w-4"
            />
            <span>
              Anchors ({anchors.length})
              {selectedIds.size > 0 && ` • ${selectedIds.size} selected`}
            </span>
          </div>
          <span className="hidden md:inline">
            Click to flag irrelevant anchors before keyword generation.
          </span>
        </div>

        <div className="divide-y divide-gray-200 dark:divide-gray-800">
          {isLoading && (
            <div className="px-4 py-6 text-sm text-gray-600 dark:text-gray-400">
              Loading anchors...
            </div>
          )}

          {!isLoading && anchors.length === 0 && (
            <div className="px-4 py-6 text-sm text-gray-600 dark:text-gray-400">
              No anchors found for this campaign yet. Run Scout to populate anchors.
            </div>
          )}

          {!isLoading &&
            anchors.map((anchor) => {
              const checked = selectedIds.has(anchor.id);
              const address =
                anchor.metadata?.address ||
                anchor.metadata?.formatted_address ||
                "";
              const relevanceHint = anchor.metadata?.source_query || "";

              return (
                <button
                  key={anchor.id}
                  type="button"
                  onClick={() => toggleOne(anchor.id)}
                  className={`flex w-full items-center justify-between px-4 py-3 text-left transition ${
                    checked
                      ? "bg-blue-50 dark:bg-blue-900/20"
                      : "hover:bg-gray-50 dark:hover:bg-gray-900"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleOne(anchor.id)}
                      className="mt-1 h-4 w-4"
                      onClick={(e) => e.stopPropagation()}
                    />
                    <div>
                      <p className="text-sm font-medium text-gray-900 dark:text-white">
                        {anchor.name}
                      </p>
                      {address && (
                        <p className="text-xs text-gray-600 dark:text-gray-400">
                          {address}
                        </p>
                      )}
                      {relevanceHint && (
                        <p className="mt-1 text-[11px] text-gray-500 dark:text-gray-500">
                          Source query: {relevanceHint}
                        </p>
                      )}
                    </div>
                  </div>
                  {anchor.metadata?.google_maps_url && (
                    <a
                      href={anchor.metadata.google_maps_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-600 hover:underline dark:text-blue-400"
                      onClick={(e) => e.stopPropagation()}
                    >
                      Maps →
                    </a>
                  )}
                </button>
              );
            })}
        </div>
      </Card>
    </div>
  );
}

