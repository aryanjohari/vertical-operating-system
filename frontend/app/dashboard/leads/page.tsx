"use client";

import { useState } from "react";
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
import { useLeads } from "@/hooks/useLeads";
import { useProjectContext } from "@/hooks/useProjectContext";
import { getAuthUser } from "@/lib/auth";
import { getLeads, createProject } from "@/lib/api";
import { Plus, Edit2, Trash2, X, Save, Loader2 } from "lucide-react";
import type { Entity } from "@/lib/types";

interface LeadFormData {
  name: string;
  email: string;
  phone: string;
  source: string;
  notes: string;
}

export default function LeadsPage() {
  const { projectId } = useProjectContext();
  const { leads, isLoading, mutate } = useLeads(projectId);
  const user_id = getAuthUser() || "admin";

  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [formData, setFormData] = useState<LeadFormData>({
    name: "",
    email: "",
    phone: "",
    source: "",
    notes: "",
  });
  const [editFormData, setEditFormData] = useState<LeadFormData>({
    name: "",
    email: "",
    phone: "",
    source: "",
    notes: "",
  });

  const resetForm = () => {
    setFormData({
      name: "",
      email: "",
      phone: "",
      source: "",
      notes: "",
    });
    setIsCreating(false);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectId) {
      alert("Please select a project first");
      return;
    }

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/leads`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id,
          project_id: projectId,
          source: formData.source || "Manual Entry",
          data: {
            name: formData.name,
            email: formData.email,
            phone: formData.phone,
            notes: formData.notes,
          },
        }),
      });

      if (response.ok) {
        resetForm();
        mutate();
      } else {
        const errorData = await response.json();
        alert(errorData.detail || "Failed to create lead");
      }
    } catch (error) {
      console.error("Error creating lead:", error);
      alert("Error creating lead");
    }
  };

  const startEdit = (lead: Entity) => {
    setEditingId(lead.id || null);
    setEditFormData({
      name: lead.name || "",
      email: lead.metadata?.email || lead.primary_contact || "",
      phone: lead.metadata?.phone || "",
      source: lead.metadata?.source || "",
      notes: lead.metadata?.notes || "",
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditFormData({
      name: "",
      email: "",
      phone: "",
      source: "",
      notes: "",
    });
  };

  const handleUpdate = async (leadId: string) => {
    try {
      const { updateEntity } = await import("@/lib/api");
      const success = await updateEntity(leadId, {
        name: editFormData.name,
        primary_contact: editFormData.email,
        metadata: {
          email: editFormData.email,
          phone: editFormData.phone,
          source: editFormData.source,
          notes: editFormData.notes,
        },
      });

      if (success) {
        cancelEdit();
        mutate();
      } else {
        alert("Failed to update lead");
      }
    } catch (error) {
      console.error("Error updating lead:", error);
      alert("Error updating lead");
    }
  };

  const handleDelete = async (leadId: string) => {
    if (!leadId || deletingIds.has(leadId)) return;

    if (!confirm("Are you sure you want to delete this lead?")) {
      return;
    }

    setDeletingIds((prev) => new Set(prev).add(leadId));

    try {
      const { deleteEntity } = await import("@/lib/api");
      const success = await deleteEntity(leadId, user_id);
      if (success) {
        mutate();
      } else {
        alert("Failed to delete lead");
      }
    } catch (error) {
      console.error("Error deleting lead:", error);
      alert("Error deleting lead");
    } finally {
      setDeletingIds((prev) => {
        const next = new Set(prev);
        next.delete(leadId);
        return next;
      });
    }
  };

  return (
    <div className="p-4 md:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold text-purple-400">Leads Management</h1>
            <p className="text-slate-400 mt-1">Manage your captured leads</p>
          </div>
          <Button
            onClick={() => setIsCreating(true)}
            className="bg-purple-600 hover:bg-purple-700 text-white"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Lead
          </Button>
        </div>

        {/* Create Form */}
        {isCreating && (
          <Card className="border-purple-500/30 bg-slate-900/50">
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle className="text-purple-400">Create New Lead</CardTitle>
                <Button variant="ghost" size="sm" onClick={resetForm}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreate} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      className="bg-slate-800 border-purple-500/30 text-slate-100"
                    />
                  </div>
                  <div>
                    <Label htmlFor="phone">Phone</Label>
                    <Input
                      id="phone"
                      type="tel"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      className="bg-slate-800 border-purple-500/30 text-slate-100"
                    />
                  </div>
                  <div>
                    <Label htmlFor="source">Source</Label>
                    <Input
                      id="source"
                      value={formData.source}
                      onChange={(e) => setFormData({ ...formData, source: e.target.value })}
                      placeholder="e.g., Website Form, Phone Call"
                      className="bg-slate-800 border-purple-500/30 text-slate-100"
                    />
                  </div>
                </div>
                <div>
                  <Label htmlFor="notes">Notes</Label>
                  <textarea
                    id="notes"
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 bg-slate-800 border border-purple-500/30 rounded-md text-slate-100 focus:outline-none focus:ring-2 focus:ring-purple-500/50"
                  />
                </div>
                <div className="flex gap-2">
                  <Button type="submit" className="bg-purple-600 hover:bg-purple-700">
                    <Save className="w-4 h-4 mr-2" />
                    Create Lead
                  </Button>
                  <Button type="button" variant="outline" onClick={resetForm}>
                    Cancel
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Leads Table */}
        <Card className="border-purple-500/30 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="text-purple-400">All Leads</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="text-center py-8 text-slate-400">
                <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />
                Loading leads...
              </div>
            ) : leads.length === 0 ? (
              <div className="text-center py-8 text-slate-400">
                No leads found. Create your first lead to get started.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead className="hidden sm:table-cell">Email</TableHead>
                      <TableHead className="hidden md:table-cell">Phone</TableHead>
                      <TableHead className="hidden lg:table-cell">Source</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {leads.map((lead) => (
                      <TableRow key={lead.id}>
                        {editingId === lead.id ? (
                          <>
                            <TableCell colSpan={4}>
                              <div className="space-y-2">
                                <Input
                                  value={editFormData.name}
                                  onChange={(e) =>
                                    setEditFormData({ ...editFormData, name: e.target.value })
                                  }
                                  className="bg-slate-800 border-purple-500/30 text-slate-100"
                                  placeholder="Name"
                                />
                                <div className="grid grid-cols-2 gap-2">
                                  <Input
                                    value={editFormData.email}
                                    onChange={(e) =>
                                      setEditFormData({ ...editFormData, email: e.target.value })
                                    }
                                    className="bg-slate-800 border-purple-500/30 text-slate-100"
                                    placeholder="Email"
                                  />
                                  <Input
                                    value={editFormData.phone}
                                    onChange={(e) =>
                                      setEditFormData({ ...editFormData, phone: e.target.value })
                                    }
                                    className="bg-slate-800 border-purple-500/30 text-slate-100"
                                    placeholder="Phone"
                                  />
                                </div>
                              </div>
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex gap-2 justify-end">
                                <Button
                                  size="sm"
                                  onClick={() => lead.id && handleUpdate(lead.id)}
                                  className="bg-purple-600 hover:bg-purple-700"
                                >
                                  <Save className="w-4 h-4" />
                                </Button>
                                <Button size="sm" variant="outline" onClick={cancelEdit}>
                                  <X className="w-4 h-4" />
                                </Button>
                              </div>
                            </TableCell>
                          </>
                        ) : (
                          <>
                            <TableCell className="font-medium text-purple-300">
                              {lead.name}
                            </TableCell>
                            <TableCell className="hidden sm:table-cell text-slate-400">
                              {lead.metadata?.email || lead.primary_contact || "—"}
                            </TableCell>
                            <TableCell className="hidden md:table-cell text-slate-400">
                              {lead.metadata?.phone || "—"}
                            </TableCell>
                            <TableCell className="hidden lg:table-cell text-slate-400">
                              {lead.metadata?.source || "—"}
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex gap-2 justify-end">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => lead && startEdit(lead)}
                                >
                                  <Edit2 className="w-4 h-4" />
                                </Button>
                                <Button
                                  size="sm"
                                  variant="destructive"
                                  onClick={() => lead.id && handleDelete(lead.id)}
                                  disabled={lead.id ? deletingIds.has(lead.id) : true}
                                >
                                  {lead.id && deletingIds.has(lead.id) ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                  ) : (
                                    <Trash2 className="w-4 h-4" />
                                  )}
                                </Button>
                              </div>
                            </TableCell>
                          </>
                        )}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
