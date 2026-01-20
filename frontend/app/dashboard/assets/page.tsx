"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getEntities, createEntity, updateEntity, deleteEntity } from "@/lib/api";
import { getAuthUser } from "@/lib/auth";
import { useProjectContext } from "@/hooks/useProjectContext";
import { Plus, Edit2, Trash2, X, Save, Loader2 } from "lucide-react";
import type { Entity } from "@/lib/types";

type EntityType = "anchor_location" | "seo_keyword" | "page_draft";

interface EntityFormData {
  name: string;
  primary_contact: string;
  metadata: Record<string, any>;
}

export default function AssetsPage() {
  const { projectId } = useProjectContext();
  const user_id = getAuthUser() || "admin";

  const [selectedType, setSelectedType] = useState<EntityType>("anchor_location");
  const [entities, setEntities] = useState<Entity[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [formData, setFormData] = useState<EntityFormData>({
    name: "",
    primary_contact: "",
    metadata: {},
  });
  const [editFormData, setEditFormData] = useState<EntityFormData>({
    name: "",
    primary_contact: "",
    metadata: {},
  });

  useEffect(() => {
    loadEntities();
  }, [selectedType, projectId]);

  const loadEntities = async () => {
    setIsLoading(true);
    try {
      const data = await getEntities(user_id, selectedType, projectId || undefined);
      setEntities(data);
    } catch (error) {
      console.error("Error loading entities:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: "",
      primary_contact: "",
      metadata: {},
    });
    setIsCreating(false);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      alert("Name is required");
      return;
    }

    try {
      const newEntity = await createEntity(user_id, selectedType, {
        name: formData.name,
        primary_contact: formData.primary_contact,
        metadata: formData.metadata,
        project_id: projectId || undefined,
      });

      if (newEntity) {
        resetForm();
        loadEntities();
      }
    } catch (error) {
      console.error("Error creating entity:", error);
      alert("Error creating entity");
    }
  };

  const startEdit = (entity: Entity) => {
    setEditingId(entity.id || null);
    setEditFormData({
      name: entity.name || "",
      primary_contact: entity.primary_contact || "",
      metadata: entity.metadata || {},
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditFormData({
      name: "",
      primary_contact: "",
      metadata: {},
    });
  };

  const handleUpdate = async (entityId: string) => {
    try {
      const success = await updateEntity(entityId, {
        name: editFormData.name,
        primary_contact: editFormData.primary_contact,
        ...editFormData.metadata,
      });

      if (success) {
        cancelEdit();
        loadEntities();
      } else {
        alert("Failed to update entity");
      }
    } catch (error) {
      console.error("Error updating entity:", error);
      alert("Error updating entity");
    }
  };

  const handleDelete = async (entityId: string) => {
    if (!entityId || deletingIds.has(entityId)) return;

    if (!confirm("Are you sure you want to delete this item?")) {
      return;
    }

    setDeletingIds((prev) => new Set(prev).add(entityId));

    try {
      const success = await deleteEntity(entityId, user_id);
      if (success) {
        loadEntities();
      } else {
        alert("Failed to delete entity");
      }
    } catch (error) {
      console.error("Error deleting entity:", error);
      alert("Error deleting entity");
    } finally {
      setDeletingIds((prev) => {
        const next = new Set(prev);
        next.delete(entityId);
        return next;
      });
    }
  };

  const renderEntityRow = (entity: Entity) => {
    if (editingId === entity.id) {
      return (
        <TableRow key={entity.id}>
          <TableCell colSpan={selectedType === "page_draft" ? 4 : 3}>
            <div className="space-y-2">
              <Input
                value={editFormData.name}
                onChange={(e) =>
                  setEditFormData({ ...editFormData, name: e.target.value })
                }
                className="bg-slate-800 border-purple-500/30 text-slate-100"
                placeholder="Name"
              />
              <Input
                value={editFormData.primary_contact}
                onChange={(e) =>
                  setEditFormData({ ...editFormData, primary_contact: e.target.value })
                }
                className="bg-slate-800 border-purple-500/30 text-slate-100"
                placeholder="Contact"
              />
            </div>
          </TableCell>
          <TableCell className="text-right">
            <div className="flex gap-2 justify-end">
              <Button
                size="sm"
                onClick={() => entity.id && handleUpdate(entity.id)}
                className="bg-purple-600 hover:bg-purple-700"
              >
                <Save className="w-4 h-4" />
              </Button>
              <Button size="sm" variant="outline" onClick={cancelEdit}>
                <X className="w-4 h-4" />
              </Button>
            </div>
          </TableCell>
        </TableRow>
      );
    }

    if (selectedType === "anchor_location") {
      return (
        <TableRow key={entity.id}>
          <TableCell className="font-medium text-purple-300">
            {entity.name}
          </TableCell>
          <TableCell className="text-slate-400">
            {entity.metadata?.address || "—"}
          </TableCell>
          <TableCell className="text-slate-400">
            {entity.primary_contact || entity.metadata?.phone || "—"}
          </TableCell>
          <TableCell className="text-right">
            <div className="flex gap-2 justify-end">
              <Button
                size="sm"
                variant="outline"
                onClick={() => entity && startEdit(entity)}
              >
                <Edit2 className="w-4 h-4" />
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => entity.id && handleDelete(entity.id)}
                disabled={entity.id ? deletingIds.has(entity.id) : true}
              >
                {entity.id && deletingIds.has(entity.id) ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
              </Button>
            </div>
          </TableCell>
        </TableRow>
      );
    }

    if (selectedType === "seo_keyword") {
      return (
        <TableRow key={entity.id}>
          <TableCell className="font-medium text-purple-300">
            {entity.name}
          </TableCell>
          <TableCell className="text-slate-400">
            {entity.metadata?.target_anchor || "—"}
          </TableCell>
          <TableCell className="text-slate-400">
            <span className="px-2 py-1 rounded text-xs bg-slate-800 text-slate-300">
              {entity.metadata?.status || "pending"}
            </span>
          </TableCell>
          <TableCell className="text-right">
            <div className="flex gap-2 justify-end">
              <Button
                size="sm"
                variant="outline"
                onClick={() => entity && startEdit(entity)}
              >
                <Edit2 className="w-4 h-4" />
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => entity.id && handleDelete(entity.id)}
                disabled={entity.id ? deletingIds.has(entity.id) : true}
              >
                {entity.id && deletingIds.has(entity.id) ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
              </Button>
            </div>
          </TableCell>
        </TableRow>
      );
    }

    // page_draft
    return (
      <TableRow key={entity.id}>
        <TableCell className="font-medium text-purple-300">
          {entity.name || "Untitled Page"}
        </TableCell>
        <TableCell className="text-slate-400">
          <span className="px-2 py-1 rounded text-xs bg-slate-800 text-slate-300">
            {entity.metadata?.status || "draft"}
          </span>
        </TableCell>
        <TableCell className="text-slate-400 font-mono text-sm">
          {entity.metadata?.slug || "—"}
        </TableCell>
        <TableCell className="text-right">
          <div className="flex gap-2 justify-end">
            <Button
              size="sm"
              variant="outline"
              onClick={() => entity && startEdit(entity)}
            >
              <Edit2 className="w-4 h-4" />
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => entity.id && handleDelete(entity.id)}
              disabled={entity.id ? deletingIds.has(entity.id) : true}
            >
              {entity.id && deletingIds.has(entity.id) ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4" />
              )}
            </Button>
          </div>
        </TableCell>
      </TableRow>
    );
  };

  const getTableHeaders = () => {
    if (selectedType === "anchor_location") {
      return (
        <>
          <TableHead>Name</TableHead>
          <TableHead className="hidden sm:table-cell">Address</TableHead>
          <TableHead className="hidden md:table-cell">Contact</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </>
      );
    }
    if (selectedType === "seo_keyword") {
      return (
        <>
          <TableHead>Keyword</TableHead>
          <TableHead className="hidden sm:table-cell">Target Location</TableHead>
          <TableHead className="hidden md:table-cell">Status</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </>
      );
    }
    // page_draft
    return (
      <>
        <TableHead>Title</TableHead>
        <TableHead className="hidden sm:table-cell">Status</TableHead>
        <TableHead className="hidden md:table-cell">Slug</TableHead>
        <TableHead className="text-right">Actions</TableHead>
      </>
    );
  };

  return (
    <div className="p-4 md:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold text-purple-400">Content Library</h1>
            <p className="text-slate-400 mt-1">Manage all your assets</p>
          </div>
          <Button
            onClick={() => setIsCreating(true)}
            className="bg-purple-600 hover:bg-purple-700 text-white"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Asset
          </Button>
        </div>

        {/* Type Selector */}
        <Card className="border-purple-500/30 bg-slate-900/50">
          <CardContent className="pt-6">
            <div className="flex gap-2 flex-wrap">
              <Button
                variant={selectedType === "anchor_location" ? "default" : "outline"}
                onClick={() => setSelectedType("anchor_location")}
                size="sm"
              >
                Anchor Locations
              </Button>
              <Button
                variant={selectedType === "seo_keyword" ? "default" : "outline"}
                onClick={() => setSelectedType("seo_keyword")}
                size="sm"
              >
                SEO Keywords
              </Button>
              <Button
                variant={selectedType === "page_draft" ? "default" : "outline"}
                onClick={() => setSelectedType("page_draft")}
                size="sm"
              >
                Page Drafts
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Create Form */}
        {isCreating && (
          <Card className="border-purple-500/30 bg-slate-900/50">
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle className="text-purple-400">
                  Create New {selectedType.replace("_", " ")}
                </CardTitle>
                <Button variant="ghost" size="sm" onClick={resetForm}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreate} className="space-y-4">
                <div>
                  <Label htmlFor="name">Name *</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                    className="bg-slate-800 border-purple-500/30 text-slate-100"
                  />
                </div>
                <div>
                  <Label htmlFor="contact">Contact</Label>
                  <Input
                    id="contact"
                    value={formData.primary_contact}
                    onChange={(e) =>
                      setFormData({ ...formData, primary_contact: e.target.value })
                    }
                    className="bg-slate-800 border-purple-500/30 text-slate-100"
                  />
                </div>
                <div className="flex gap-2">
                  <Button type="submit" className="bg-purple-600 hover:bg-purple-700">
                    <Save className="w-4 h-4 mr-2" />
                    Create
                  </Button>
                  <Button type="button" variant="outline" onClick={resetForm}>
                    Cancel
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Entities Table */}
        <Card className="border-purple-500/30 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="text-purple-400">
              {selectedType.replace("_", " ").replace(/\b\w/g, (l) => l.toUpperCase())}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="text-center py-8 text-slate-400">
                <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />
                Loading...
              </div>
            ) : entities.length === 0 ? (
              <div className="text-center py-8 text-slate-400">
                No {selectedType.replace("_", " ")} found
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>{getTableHeaders()}</TableRow>
                  </TableHeader>
                  <TableBody>{entities.map(renderEntityRow)}</TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
