// components/entities/EntityManager.tsx
"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import api from "@/lib/api";
import { Entity } from "@/lib/types";
import EntityTable from "./EntityTable";
import EntityForm from "./EntityForm";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Modal from "@/components/ui/Modal";
import Card from "@/components/ui/Card";

interface EntityManagerProps {
  projectId: string;
}

export default function EntityManager({ projectId }: EntityManagerProps) {
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [filterType, setFilterType] = useState<string>(
    searchParams?.get("filter") || "",
  );
  const [filterCampaign, setFilterCampaign] = useState<string>("");
  const [sortBy, setSortBy] = useState<"name" | "created_at" | "entity_type">(
    "created_at",
  );
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  // Fetch campaigns for filter dropdown
  const { data: campaignsData } = useQuery({
    queryKey: ["campaigns", projectId],
    queryFn: async () => {
      const response = await api.get(`/api/projects/${projectId}/campaigns`);
      return response.data.campaigns || [];
    },
  });

  const { data: entitiesData, isLoading } = useQuery({
    queryKey: ["entities", projectId, filterType, filterCampaign],
    queryFn: async () => {
      const response = await api.get(
        `/api/entities?project_id=${projectId}${filterType ? `&entity_type=${filterType}` : ""}`,
      );
      return response.data.entities || [];
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: any) => {
      const response = await api.post("/api/entities", {
        ...data,
        project_id: projectId,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entities", projectId] });
      setIsCreateModalOpen(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<Entity> }) => {
      const response = await api.put(`/api/entities/${id}`, {
        name: data.name,
        primary_contact: data.primary_contact,
        metadata: data.metadata,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entities", projectId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      const response = await api.delete(`/api/entities/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entities", projectId] });
    },
  });

  const handleCreate = async (data: any) => {
    await createMutation.mutateAsync(data);
  };

  const handleUpdate = async (id: string, data: Partial<Entity>) => {
    await updateMutation.mutateAsync({ id, data });
  };

  const handleDelete = async (id: string) => {
    await deleteMutation.mutateAsync(id);
  };

  const allEntities = entitiesData || [];

  // Filter by campaign_id in metadata
  const filteredEntities = useMemo(() => {
    let filtered = allEntities;

    if (filterCampaign) {
      filtered = filtered.filter(
        (e: Entity) => e.metadata?.campaign_id === filterCampaign,
      );
    }

    // Sort entities
    filtered = [...filtered].sort((a: Entity, b: Entity) => {
      let aVal: any;
      let bVal: any;

      if (sortBy === "name") {
        aVal = a.name.toLowerCase();
        bVal = b.name.toLowerCase();
      } else if (sortBy === "created_at") {
        aVal = new Date(a.created_at).getTime();
        bVal = new Date(b.created_at).getTime();
      } else {
        aVal = a.entity_type.toLowerCase();
        bVal = b.entity_type.toLowerCase();
      }

      if (sortOrder === "asc") {
        return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
      } else {
        return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
      }
    });

    return filtered;
  }, [allEntities, filterCampaign, sortBy, sortOrder]);

  const entityTypes: string[] = Array.from(
    new Set(allEntities.map((e: Entity) => e.entity_type)),
  );
  const campaigns = campaignsData || [];

  if (isLoading) {
    return <div className="text-center py-8">Loading entities...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Filters and Actions */}
      <Card className="p-4">
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-4 flex-1 flex-wrap">
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">
                  Filter by type:
                </label>
                <select
                  value={filterType}
                  onChange={(e) => setFilterType(e.target.value)}
                  className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">All Types</option>
                  {entityTypes.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
              </div>

              {campaigns.length > 0 && (
                <div className="flex items-center gap-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">
                    Filter by campaign:
                  </label>
                  <select
                    value={filterCampaign}
                    onChange={(e) => setFilterCampaign(e.target.value)}
                    className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">All Campaigns</option>
                    {campaigns.map((campaign: any) => (
                      <option key={campaign.id} value={campaign.id}>
                        {campaign.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">
                  Sort by:
                </label>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as any)}
                  className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="created_at">Created Date</option>
                  <option value="name">Name</option>
                  <option value="entity_type">Type</option>
                </select>
                <button
                  onClick={() =>
                    setSortOrder(sortOrder === "asc" ? "desc" : "asc")
                  }
                  className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-700"
                  title={sortOrder === "asc" ? "Ascending" : "Descending"}
                >
                  {sortOrder === "asc" ? "↑" : "↓"}
                </button>
              </div>
            </div>
            <Button onClick={() => setIsCreateModalOpen(true)}>
              Create Entity
            </Button>
          </div>

          {filteredEntities.length !== allEntities.length && (
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Showing {filteredEntities.length} of {allEntities.length} entities
            </div>
          )}
        </div>
      </Card>

      {/* Entity Table */}
      <EntityTable
        entities={filteredEntities}
        onUpdate={handleUpdate}
        onDelete={handleDelete}
        projectId={projectId}
      />

      {/* Create Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create New Entity"
      >
        <EntityForm
          onSubmit={handleCreate}
          onCancel={() => setIsCreateModalOpen(false)}
          isLoading={createMutation.isPending}
        />
      </Modal>
    </div>
  );
}
