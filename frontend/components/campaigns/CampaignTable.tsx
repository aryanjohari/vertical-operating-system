"use client";

import React from "react";
import DataTable from "@/components/dashboard/DataTable";
import StatusBadge from "@/components/dashboard/StatusBadge";

export interface CampaignRow {
  id: string;
  name: string;
  module: string;
  status: string;
}

interface CampaignTableProps {
  campaigns: CampaignRow[];
  filterPlaceholder?: string;
}

export default function CampaignTable({
  campaigns,
  filterPlaceholder = "Filter campaigns...",
}: CampaignTableProps) {
  return (
    <DataTable<CampaignRow>
      columns={[
        { id: "name", header: "Name", accessorKey: "name" },
        { id: "module", header: "Module", accessorKey: "module" },
        {
          id: "status",
          header: "Status",
          accessorKey: "status",
          cell: (row: CampaignRow) => (
            <StatusBadge
              status={
                row.status === "ACTIVE"
                  ? "active"
                  : row.status === "DRAFT"
                    ? "draft"
                    : "pending"
              }
            />
          ),
        },
      ]}
      data={campaigns}
      filterPlaceholder={filterPlaceholder}
    />
  );
}
