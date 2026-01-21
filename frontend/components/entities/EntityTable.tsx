// components/entities/EntityTable.tsx
'use client';

import React, { useState } from 'react';
import { Entity } from '@/lib/types';
import Button from '@/components/ui/Button';
import Modal from '@/components/ui/Modal';
import EntityForm from './EntityForm';

interface EntityTableProps {
  entities: Entity[];
  onUpdate: (id: string, data: Partial<Entity>) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  projectId: string;
}

export default function EntityTable({ entities, onUpdate, onDelete, projectId }: EntityTableProps) {
  const [editingEntity, setEditingEntity] = useState<Entity | null>(null);
  const [deletingEntity, setDeletingEntity] = useState<Entity | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  const handleEdit = (entity: Entity) => {
    setEditingEntity(entity);
  };

  const handleDelete = async () => {
    if (deletingEntity) {
      await onDelete(deletingEntity.id);
      setDeletingEntity(null);
    }
  };

  const handleFormSubmit = async (data: any) => {
    if (editingEntity) {
      await onUpdate(editingEntity.id, data);
      setEditingEntity(null);
    }
  };

  if (entities.length === 0) {
    return (
      <div className="text-center py-8 text-gray-600 dark:text-gray-400">
        No entities found. Create one to get started.
      </div>
    );
  }

  return (
    <>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Type
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Contact
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Created
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            {entities.map((entity) => (
              <React.Fragment key={entity.id}>
                <tr className="hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="px-2 py-1 text-xs font-medium rounded-full bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-300">
                      {entity.entity_type}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm font-medium text-gray-900 dark:text-white">
                      {entity.name}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {entity.primary_contact || '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {new Date(entity.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => toggleRow(entity.id)}
                        className="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300"
                      >
                        {expandedRows.has(entity.id) ? 'Hide' : 'View'}
                      </button>
                      <button
                        onClick={() => handleEdit(entity)}
                        className="text-indigo-600 hover:text-indigo-900 dark:text-indigo-400 dark:hover:text-indigo-300"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => setDeletingEntity(entity)}
                        className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
                {expandedRows.has(entity.id) && (
                  <tr>
                    <td colSpan={5} className="px-6 py-4 bg-gray-50 dark:bg-gray-900">
                      <div className="text-sm">
                        <div className="font-semibold mb-2 text-gray-900 dark:text-white">
                          Metadata:
                        </div>
                        <pre className="bg-white dark:bg-gray-800 p-4 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto">
                          {JSON.stringify(entity.metadata, null, 2)}
                        </pre>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Edit Modal */}
      <Modal
        isOpen={!!editingEntity}
        onClose={() => setEditingEntity(null)}
        title="Edit Entity"
      >
        {editingEntity && (
          <EntityForm
            entity={editingEntity}
            onSubmit={handleFormSubmit}
            onCancel={() => setEditingEntity(null)}
          />
        )}
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={!!deletingEntity}
        onClose={() => setDeletingEntity(null)}
        title="Delete Entity"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeletingEntity(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDelete}>
              Delete
            </Button>
          </>
        }
      >
        <p className="text-gray-700 dark:text-gray-300">
          Are you sure you want to delete <strong>{deletingEntity?.name}</strong>? This action
          cannot be undone.
        </p>
      </Modal>
    </>
  );
}
