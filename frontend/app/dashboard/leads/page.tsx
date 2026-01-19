"use client";

import { useLeads } from "@/hooks/useLeads";
import { useProjectContext } from "@/hooks/useProjectContext";
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
  const { projectId } = useProjectContext();
  const { leads, isLoading, mutate } = useLeads(projectId);

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

  const getName = (lead: any) => {
    return lead.metadata?.fullName || lead.metadata?.name || lead.name || "Unknown";
  };

  const getPhone = (lead: any) => {
    return lead.metadata?.phoneNumber || lead.metadata?.from_number || lead.primary_contact || "N/A";
  };

  const getSource = (lead: any) => {
    return lead.metadata?.source || lead.name || "Unknown";
  };

  const getRecordingUrl = (lead: any) => {
    return lead.metadata?.recording_url;
  };

  const handleRefresh = () => {
    mutate();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-purple-400">Lead CRM</h1>
          <p className="text-slate-400 mt-1">
            {projectId 
              ? `Viewing leads for current project (${leads.length} total)`
              : "Select a project to view leads"}
          </p>
        </div>
        <Button onClick={handleRefresh} variant="outline" size="sm">
          🔄 Refresh
        </Button>
      </div>

      {!projectId ? (
        <Card className="border-purple-500/30 bg-slate-900/50">
          <CardContent className="py-8">
            <div className="text-center text-slate-400">
              Please select a project from the sidebar to view leads.
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="border-purple-500/30 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="text-purple-300">Captured Leads</CardTitle>
            <CardDescription className="text-slate-400">
              All leads for the current project ({leads.length} total)
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="text-center py-8 text-slate-400">Loading leads...</div>
            ) : leads.length === 0 ? (
              <div className="text-center py-8 text-slate-400">
                No leads captured yet. Leads will appear here when users submit calculators, contact forms, or voice calls.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Phone</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Recording</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {leads.map((lead) => {
                    const recordingUrl = getRecordingUrl(lead);
                    return (
                      <TableRow key={lead.id}>
                        <TableCell className="text-slate-300 text-sm">
                          {formatDate(lead.created_at)}
                        </TableCell>
                        <TableCell className="font-medium text-purple-300">
                          {getName(lead)}
                        </TableCell>
                        <TableCell className="text-slate-300 text-sm">
                          {getPhone(lead)}
                        </TableCell>
                        <TableCell className="text-slate-300 text-sm">
                          {getSource(lead)}
                        </TableCell>
                        <TableCell>
                          {recordingUrl ? (
                            <audio controls className="h-8">
                              <source src={recordingUrl} type="audio/mpeg" />
                              <source src={recordingUrl} type="audio/wav" />
                              Your browser does not support the audio element.
                            </audio>
                          ) : (
                            <span className="text-slate-500 text-sm">No recording</span>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
