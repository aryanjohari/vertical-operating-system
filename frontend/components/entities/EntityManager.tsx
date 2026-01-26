// components/entities/EntityManager.tsx
'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { Entity } from '@/lib/types';
import EntityTable from './EntityTable';
import EntityForm from './EntityForm';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Modal from '@/components/ui/Modal';
import Card from '@/components/ui/Card';

interface EntityManagerProps {
  projectId: string;
}

export default function EntityManager({ projectId }: EntityManagerProps) {
  const queryClient = useQueryClient();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [filterType, setFilterType] = useState<string>('');

  const { data: entitiesData, isLoading } = useQuery({
    queryKey: ['entities', projectId, filterType],
    queryFn: async () => {
      const response = await api.get(
        `/api/entities?project_id=${projectId}${filterType ? `&entity_type=${filterType}` : ''}`
      );
      return response.data.entities || [];
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: any) => {
      const response = await api.post('/api/entities', {
        ...data,
        project_id: projectId,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entities', projectId] });
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
      queryClient.invalidateQueries({ queryKey: ['entities', projectId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      const response = await api.delete(`/api/entities/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entities', projectId] });
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

  const entities = entitiesData || [];
  const entityTypes: string[] = Array.from(new Set(entities.map((e: Entity) => e.entity_type)));

  if (isLoading) {
    return <div className="text-center py-8">Loading entities...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Filters and Actions */}
      <Card className="p-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-4 flex-1">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
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
          <Button onClick={() => setIsCreateModalOpen(true)}>Create Entity</Button>
        </div>
      </Card>

      {/* Entity Table */}
      <EntityTable
        entities={entities}
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
