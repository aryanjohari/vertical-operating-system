"use client";

import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { Entity } from "@/lib/types";

interface AssetTableProps {
  entities: Entity[];
  entityType: "anchor_location" | "seo_keyword" | "page_draft";
  isLoading: boolean;
}

export function AssetTable({ entities, entityType, isLoading }: AssetTableProps) {
  if (isLoading) {
    return (
      <div className="text-center py-8 text-slate-400">Loading data...</div>
    );
  }

  if (entities.length === 0) {
    return (
      <div className="text-center py-8 text-slate-400">
        No {entityType.replace("_", " ")} found. Waiting for agents...
      </div>
    );
  }

  const getStatusBadge = (status: string) => {
    if (status === "pending") return <Badge variant="pending">Pending</Badge>;
    if (status === "published" || status === "live")
      return <Badge variant="live">Live</Badge>;
    return <Badge variant="outline">{status}</Badge>;
  };

  if (entityType === "anchor_location") {
    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Phone</TableHead>
            <TableHead>Address</TableHead>
            <TableHead>Website</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entities.map((entity) => (
            <TableRow key={entity.id}>
              <TableCell className="font-medium text-purple-300">
                {entity.name}
              </TableCell>
              <TableCell>{entity.primary_contact || "N/A"}</TableCell>
              <TableCell>{entity.metadata?.address || "N/A"}</TableCell>
              <TableCell>{entity.metadata?.website || "N/A"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  }

  if (entityType === "seo_keyword") {
    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Keyword</TableHead>
            <TableHead>Target Location</TableHead>
            <TableHead>City</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entities.map((entity) => (
            <TableRow key={entity.id}>
              <TableCell className="font-medium text-purple-300">
                {entity.name}
              </TableCell>
              <TableCell>{entity.metadata?.target_anchor || "N/A"}</TableCell>
              <TableCell>{entity.metadata?.city || "N/A"}</TableCell>
              <TableCell>
                {getStatusBadge(entity.metadata?.status || "pending")}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  }

  if (entityType === "page_draft") {
    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Title</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Created</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entities.map((entity) => (
            <TableRow key={entity.id}>
              <TableCell className="font-medium text-purple-300">
                {entity.name || "Untitled Page"}
              </TableCell>
              <TableCell>
                {getStatusBadge(entity.metadata?.status || "draft")}
              </TableCell>
              <TableCell>
                {new Date(entity.created_at).toLocaleDateString()}
              </TableCell>
              <TableCell>
                <span className="text-xs text-slate-500">View</span>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  }

  return null;
}
