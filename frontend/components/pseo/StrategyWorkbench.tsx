"use client";

import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { Entity } from "@/lib/types";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

interface StrategyWorkbenchProps {
  projectId: string;
  campaignId: string;
}

type KeywordStatus = "pending" | "approved" | "excluded" | string;

export default function StrategyWorkbench({
  projectId,
  campaignId,
}: StrategyWorkbenchProps) {
  const queryClient = useQueryClient();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [targetStatus, setTargetStatus] = useState<KeywordStatus>("approved");

  const { data: entities, isLoading } = useQuery({
    queryKey: ["entities", projectId, "seo_keyword"],
    queryFn: async () => {
      const response = await api.get("/api/entities", {
        params: {
          project_id: projectId,
          entity_type: "seo_keyword",
        },
      });
      const all: Entity[] = response.data.entities || [];
      return all.filter(
        (e) =>
          e.metadata?.campaign_id === campaignId &&
          e.metadata?.status !== "excluded",
      );
    },
  });

  const keywords = entities || [];

  const clusters = useMemo(() => {
    const groups: Record<string, Entity[]> = {};
    for (const kw of keywords) {
      const intent = kw.metadata?.intent || "Other";
      if (!groups[intent]) groups[intent] = [];
      groups[intent].push(kw);
    }
    return groups;
  }, [keywords]);

  const approvedCount = useMemo(
    () =>
      keywords.filter((k) => (k.metadata?.status as KeywordStatus) === "approved")
        .length,
    [keywords],
  );

  const mutation = useMutation({
    mutationFn: async (ids: string[]) => {
      if (ids.length === 0) return;
      await api.post("/api/run", {
        task: "manager",
        user_id: "",
        params: {
          project_id: projectId,
          campaign_id: campaignId,
          action: "strategy_review",
          ids,
          status: targetStatus,
        },
      });
    },
    onSuccess: async () => {
      setSelectedIds(new Set());
      await queryClient.invalidateQueries({
        queryKey: ["entities", projectId, "seo_keyword"],
      });
    },
  });

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

  const toggleCluster = (clusterKey: string) => {
    const clusterItems = clusters[clusterKey] || [];
    const allSelected = clusterItems.every((c) => selectedIds.has(c.id));
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allSelected) {
        clusterItems.forEach((c) => next.delete(c.id));
      } else {
        clusterItems.forEach((c) => next.add(c.id));
      }
      return next;
    });
  };

  const handleApplyToSelection = () => {
    mutation.mutate(Array.from(selectedIds));
  };

  const handleApproveCluster = (clusterKey: string) => {
    const clusterItems = clusters[clusterKey] || [];
    if (clusterItems.length === 0) return;
    setTargetStatus("approved");
    mutation.mutate(clusterItems.map((c) => c.id));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Strategy Board
          </h2>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Grouped intent clusters from Strategist. Approve the clusters you want to fund.
          </p>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-500">
            Approved keywords:{" "}
            <span className="font-semibold text-gray-900 dark:text-white">
              {approvedCount}
            </span>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={targetStatus}
            onChange={(e) =>
              setTargetStatus(e.target.value as KeywordStatus)
            }
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
          >
            <option value="approved">Approve selection</option>
            <option value="excluded">Exclude selection</option>
          </select>
          <Button
            size="sm"
            variant="primary"
            disabled={selectedIds.size === 0 || mutation.isPending}
            isLoading={mutation.isPending}
            onClick={handleApplyToSelection}
          >
            Apply to {selectedIds.size} keywords
          </Button>
        </div>
      </div>

      {isLoading && (
        <Card className="p-6 text-sm text-gray-600 dark:text-gray-400">
          Loading keywords...
        </Card>
      )}

      {!isLoading && keywords.length === 0 && (
        <Card className="p-6 text-sm text-gray-600 dark:text-gray-400">
          No keywords found for this campaign yet. Run Strategist to generate clusters.
        </Card>
      )}

      {!isLoading &&
        Object.entries(clusters).map(([clusterKey, items]) => {
          const allInClusterSelected = items.every((i) =>
            selectedIds.has(i.id),
          );
          return (
            <Card key={clusterKey} className="p-4">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => toggleCluster(clusterKey)}
                      className="flex items-center gap-2 text-sm font-semibold text-gray-900 hover:text-blue-600 dark:text-white dark:hover:text-blue-400"
                    >
                      <input
                        type="checkbox"
                        checked={allInClusterSelected}
                        onChange={() => toggleCluster(clusterKey)}
                        className="h-4 w-4"
                        onClick={(e) => e.stopPropagation()}
                      />
                      <span>{clusterKey}</span>
                    </button>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-500">
                    {items.length} keywords in this intent cluster
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => handleApproveCluster(clusterKey)}
                  disabled={mutation.isPending}
                >
                  Approve all in cluster
                </Button>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500 dark:border-gray-800 dark:text-gray-400">
                      <th className="px-2 py-2" />
                      <th className="px-2 py-2">Keyword</th>
                      <th className="px-2 py-2 hidden md:table-cell">
                        Intent Group
                      </th>
                      <th className="px-2 py-2 hidden md:table-cell">
                        Volume / Score
                      </th>
                      <th className="px-2 py-2 hidden md:table-cell">
                        Type
                      </th>
                      <th className="px-2 py-2 hidden md:table-cell">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((kw) => {
                      const checked = selectedIds.has(kw.id);
                      const status = (kw.metadata?.status ||
                        "pending") as KeywordStatus;
                      return (
                        <tr
                          key={kw.id}
                          className={`border-b border-gray-100 text-xs last:border-b-0 dark:border-gray-800 ${
                            checked
                              ? "bg-blue-50 dark:bg-blue-900/10"
                              : "hover:bg-gray-50 dark:hover:bg-gray-900"
                          }`}
                        >
                          <td className="px-2 py-2">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => toggleOne(kw.id)}
                              className="h-4 w-4"
                            />
                          </td>
                          <td className="px-2 py-2 text-gray-900 dark:text-white">
                            {kw.name}
                          </td>
                          <td className="px-2 py-2 text-gray-600 dark:text-gray-400 hidden md:table-cell">
                            {kw.metadata?.intent || clusterKey}
                          </td>
                          <td className="px-2 py-2 text-gray-600 dark:text-gray-400 hidden md:table-cell">
                            {kw.metadata?.score ?? 0}
                          </td>
                          <td className="px-2 py-2 text-gray-600 dark:text-gray-400 hidden md:table-cell">
                            {kw.metadata?.type || "-"}
                          </td>
                          <td className="px-2 py-2 hidden md:table-cell">
                            <span
                              className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${
                                status === "approved"
                                  ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                                  : status === "excluded"
                                    ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                                    : "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200"
                              }`}
                            >
                              {status}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          );
        })}
    </div>
  );
}

