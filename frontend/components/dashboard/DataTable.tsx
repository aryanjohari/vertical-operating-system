"use client";

import React, { useState, useMemo } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
  type ColumnFiltersState,
  type RowSelectionState,
} from "@tanstack/react-table";
import { cn } from "@/lib/utils";

export interface DataTableColumn<T> {
  id: string;
  header: string;
  accessorKey?: keyof T | string;
  cell?: (row: T) => React.ReactNode;
  enableSorting?: boolean;
}

interface DataTableProps<T extends { id?: string }> {
  columns: DataTableColumn<T>[];
  data: T[];
  filterPlaceholder?: string;
  onRowSelect?: (selected: T[]) => void;
  className?: string;
}

export default function DataTable<T extends { id?: string }>({
  columns,
  data,
  filterPlaceholder = "Filter...",
  onRowSelect,
  className,
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [globalFilter, setGlobalFilter] = useState("");

  const columnDefs: ColumnDef<T>[] = useMemo(
    () =>
      columns.map((col) => ({
        id: col.id,
        accessorKey: (col.accessorKey as string) ?? col.id,
        header: col.header,
        enableSorting: col.enableSorting !== false,
        cell: col.cell
          ? ({ row }) => col.cell!(row.original)
          : ({ getValue }) => (
              <span className="text-foreground">{String(getValue() ?? "")}</span>
            ),
      })),
    [columns]
  );

  const table = useReactTable({
    data,
    columns: [
      ...(onRowSelect
        ? [
            {
              id: "select",
              header: ({ table: t }) =>
                t.getIsAllPageRowsSelected() ? (
                  <input
                    type="checkbox"
                    checked
                    onChange={t.getToggleAllPageRowsSelectedHandler()}
                    className="rounded border-border"
                  />
                ) : (
                  <input
                    type="checkbox"
                    checked={false}
                    onChange={t.getToggleAllPageRowsSelectedHandler()}
                    className="rounded border-border"
                  />
                ),
              cell: ({ row }) => (
                <input
                  type="checkbox"
                  checked={row.getIsSelected()}
                  disabled={!row.getCanSelect()}
                  onChange={row.getToggleSelectedHandler()}
                  className="rounded border-border"
                />
              ),
            } as ColumnDef<T>,
          ]
        : []),
      ...columnDefs,
    ],
    state: {
      sorting,
      columnFilters,
      rowSelection,
      globalFilter,
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onRowSelectionChange: setRowSelection,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  const selectedRows = table.getFilteredSelectedRowModel().rows.map((r) => r.original);
  if (onRowSelect) {
    React.useEffect(() => {
      onRowSelect(selectedRows);
    }, [rowSelection]);
  }

  return (
    <div className={cn("w-full space-y-4", className)}>
      {columns.length > 0 && (
        <input
          type="text"
          placeholder={filterPlaceholder}
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
          className="w-full max-w-sm px-3 py-2 text-sm border rounded-lg border-border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
        />
      )}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 border-b border-border">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-4 py-3 text-left font-medium text-foreground"
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columnDefs.length + (onRowSelect ? 1 : 0)}
                  className="px-4 py-8 text-center text-muted-foreground"
                >
                  No results.
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className={cn(
                    "border-b border-border last:border-0",
                    row.getIsSelected() && "bg-muted/30"
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
              ))
            )}
          </tbody>
        </table>
      </div>
      {data.length > 10 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Page {table.getState().pagination.pageIndex + 1} of{" "}
            {table.getPageCount()}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              className="px-2 py-1 rounded border border-border disabled:opacity-50"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
              className="px-2 py-1 rounded border border-border disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
