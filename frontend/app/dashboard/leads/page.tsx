"use client";

import { useLeads } from "@/hooks/useLeads";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function LeadsPage() {
  const { leads, isLoading, mutate } = useLeads();

  const formatDate = (dateString?: string) => {
    if (!dateString) return "N/A";
    try {
      return new Date(dateString).toLocaleString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateString;
    }
  };

  const formatData = (data: Record<string, any>) => {
    // Create a readable summary from metadata
    const entries = Object.entries(data);
    if (entries.length === 0) return "No data";
    
    // Show first 3 fields as summary
    const summary = entries
      .slice(0, 3)
      .map(([key, value]) => {
        const displayValue = typeof value === "object" ? JSON.stringify(value) : String(value);
        return `${key}: ${displayValue.length > 30 ? displayValue.substring(0, 30) + "..." : displayValue}`;
      })
      .join(", ");
    
    return summary || JSON.stringify(data);
  };

  const handleRefresh = () => {
    mutate();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-purple-400">Lead Capture</h1>
          <p className="text-slate-400 mt-1">
            View captured leads from calculators and contact forms
          </p>
        </div>
        <Button onClick={handleRefresh} variant="outline" size="sm">
          🔄 Refresh
        </Button>
      </div>

      <Card className="border-purple-500/30 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-purple-300">Captured Leads</CardTitle>
          <CardDescription className="text-slate-400">
            All leads captured from interactive tools ({leads.length} total)
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-slate-400">Loading leads...</div>
          ) : leads.length === 0 ? (
            <div className="text-center py-8 text-slate-400">
              No leads captured yet. Leads will appear here when users submit calculators or contact forms.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Source</TableHead>
                  <TableHead>Captured Data</TableHead>
                  <TableHead>Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {leads.map((lead) => (
                  <TableRow key={lead.id}>
                    <TableCell className="font-medium text-purple-300">
                      {lead.name || "Unknown Source"}
                    </TableCell>
                    <TableCell className="max-w-md">
                      <div className="text-sm text-slate-300">
                        {formatData(lead.metadata || {})}
                      </div>
                      {Object.keys(lead.metadata || {}).length > 3 && (
                        <details className="mt-2">
                          <summary className="text-xs text-slate-500 cursor-pointer hover:text-purple-400">
                            View full data
                          </summary>
                          <pre className="mt-2 p-2 bg-slate-800 rounded text-xs overflow-auto max-h-48 text-slate-400">
                            {JSON.stringify(lead.metadata, null, 2)}
                          </pre>
                        </details>
                      )}
                    </TableCell>
                    <TableCell className="text-slate-300 text-sm">
                      {formatDate(lead.created_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
