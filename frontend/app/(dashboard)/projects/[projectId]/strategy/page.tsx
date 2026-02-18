"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  createColumnHelper,
  type RowSelectionState,
} from "@tanstack/react-table";
import {
  getEntities,
  createEntity,
  updateEntity,
  deleteEntity,
} from "@/lib/api";
import type { SeoKeyword } from "@/types";
import { AddKeywordsModal } from "@/components/keywords/AddKeywordsModal";
import { Plus, Check, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";


const columnHelper = createColumnHelper<SeoKeyword>();

const columns = [
  columnHelper.display({
    id: "select",
    header: ({ table }) => (
      <input
        type="checkbox"
        checked={table.getIsAllRowsSelected()}
        onChange={table.getToggleAllRowsSelectedHandler()}
        className="rounded border-border"
      />
    ),
    cell: ({ row }) => (
      <input
        type="checkbox"
        checked={row.getIsSelected()}
        onChange={row.getToggleSelectedHandler()}
        className="rounded border-border"
      />
    ),
  }),
  columnHelper.accessor((row) => row.metadata?.keyword ?? row.name, {
    id: "keyword",
    header: "Keyword",
    cell: (info) => (
      <span className="font-medium text-foreground">{info.getValue()}</span>
    ),
  }),
  columnHelper.accessor((row) => row.metadata?.search_volume as number, {
    id: "volume",
    header: "Volume",
    cell: (info) => (
      <span className="text-muted-foreground">
        {info.getValue() ?? "—"}
      </span>
    ),
  }),
  columnHelper.accessor((row) => row.metadata?.difficulty as number, {
    id: "difficulty",
    header: "Difficulty",
    cell: (info) => (
      <span className="text-muted-foreground">
        {info.getValue() ?? "—"}
      </span>
    ),
  }),
  columnHelper.accessor(
    (row) => (row.metadata?.status as string) ?? "pending",
    {
      id: "status",
      header: "Status",
      cell: (info) => {
        const s = info.getValue();
        return (
          <span
            className={cn(
              "rounded px-2 py-0.5 text-xs font-medium",
              s === "pending" || s === "pending_writer"
                ? "bg-primary/20 text-primary"
                : s === "excluded"
                  ? "bg-muted text-muted-foreground"
                  : "bg-secondary/20 text-secondary"
            )}
          >
            {s || "pending"}
          </span>
        );
      },
    }
  ),
];

function TableSkeleton() {
  return (
    <div className="glass-panel animate-pulse overflow-hidden">
      <div className="h-12 border-b border-border" />
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="flex h-12 border-b border-border last:border-0">
          <div className="w-1/4 bg-muted/50 p-3" />
          <div className="w-1/6 bg-muted/30 p-3" />
          <div className="w-1/6 bg-muted/30 p-3" />
          <div className="flex-1 bg-muted/20 p-3" />
        </div>
      ))}
    </div>
  );
}

export default function StrategyPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  const [keywords, setKeywords] = useState<SeoKeyword[]>([]);
  const [loading, setLoading] = useState(true);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [actionLoading, setActionLoading] = useState(false);

  const loadKeywords = useCallback(async () => {
    const data = await getEntities<SeoKeyword>("seo_keyword", projectId);
    setKeywords(data);
  }, [projectId]);

  useEffect(() => {
    loadKeywords()
      .catch(() => setKeywords([]))
      .finally(() => setLoading(false));
  }, [loadKeywords]);

  const table = useReactTable({
    data: keywords,
    columns,
    state: { rowSelection },
    enableRowSelection: true,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  const selectedIds = table.getSelectedRowModel().rows.map((r) => r.original.id);
  const hasSelection = selectedIds.length > 0;

  const handleApproveSelected = async () => {
    if (!hasSelection) return;
    setActionLoading(true);
    try {
      await Promise.all(
        selectedIds.map((id) =>
          updateEntity(id, { status: "pending" })
        )
      );
      setRowSelection({});
      await loadKeywords();
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteSelected = async () => {
    if (!hasSelection) return;
    if (!confirm(`Delete ${selectedIds.length} keyword(s)?`)) return;
    setActionLoading(true);
    try {
      await Promise.all(selectedIds.map((id) => deleteEntity(id)));
      setRowSelection({});
      await loadKeywords();
    } finally {
      setActionLoading(false);
    }
  };

  const handleAddKeywords = async (kwList: string[]) => {
    for (const kw of kwList) {
      await createEntity("seo_keyword", {
        name: kw,
        metadata: {
          keyword: kw,
          status: "pending",
        },
        project_id: projectId,
      });
    }
    await loadKeywords();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="acid-text text-2xl font-bold text-foreground">
          Keyword Approval
        </h1>
        <button
          type="button"
          onClick={() => setAddModalOpen(true)}
          className="acid-glow flex items-center gap-2 rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          Add Keywords
        </button>
      </div>

      {loading ? (
        <TableSkeleton />
      ) : (
        <>
          <div className="glass-panel overflow-hidden">
            <table className="w-full">
              <thead>
                {table.getHeaderGroups().map((hg) => (
                  <tr key={hg.id} className="border-b border-border">
                    {hg.headers.map((h) => (
                      <th
                        key={h.id}
                        className="px-4 py-3 text-left text-sm font-medium text-muted-foreground"
                      >
                        {flexRender(h.column.columnDef.header, h.getContext())}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    className={cn(
                      "border-b border-border transition-colors last:border-0",
                      row.getIsSelected() && "bg-primary/5"
                    )}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-4 py-3">
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {keywords.length === 0 && (
              <div className="py-12 text-center text-muted-foreground">
                No keywords yet. Add keywords to get started.
              </div>
            )}
          </div>

          {hasSelection && (
            <div className="acid-glow fixed bottom-6 left-1/2 z-40 flex -translate-x-1/2 items-center gap-3 rounded border border-primary/50 bg-background/95 px-4 py-3 backdrop-blur-sm">
              <span className="text-sm text-foreground">
                {selectedIds.length} selected
              </span>
              <button
                type="button"
                onClick={handleApproveSelected}
                disabled={actionLoading}
                className="flex items-center gap-2 rounded bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
              >
                <Check className="h-4 w-4" />
                Approve Selected
              </button>
              <button
                type="button"
                onClick={handleDeleteSelected}
                disabled={actionLoading}
                className="flex items-center gap-2 rounded border border-primary/50 px-3 py-1.5 text-sm font-medium text-primary hover:bg-primary/10 disabled:opacity-60"
              >
                <Trash2 className="h-4 w-4" />
                Delete Selected
              </button>
            </div>
          )}
        </>
      )}

      <AddKeywordsModal
        isOpen={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        onSubmit={handleAddKeywords}
      />
    </div>
  );
}
