// components/leadgen/LeadsList.tsx
'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { Entity } from '@/lib/types';
import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import Input from '@/components/ui/Input';
import Modal from '@/components/ui/Modal';

interface LeadsListProps {
  projectId: string;
  onTestCall?: (leadId: string) => void;
}

export default function LeadsList({ projectId, onTestCall }: LeadsListProps) {
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedLead, setSelectedLead] = useState<Entity | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const { data: leadsData, isLoading, refetch } = useQuery({
    queryKey: ['leads', projectId],
    queryFn: async () => {
      const response = await api.get(`/api/entities?entity_type=lead&project_id=${projectId}`);
      return response.data.entities || [];
    },
  });

  const leads: Entity[] = leadsData || [];

  const filteredLeads = leads.filter((lead) => {
    const matchesSource = sourceFilter === 'all' || lead.metadata?.source === sourceFilter;
    const matchesPriority = priorityFilter === 'all' || lead.metadata?.priority === priorityFilter;
    const matchesStatus = statusFilter === 'all' || lead.metadata?.status === statusFilter;
    const matchesSearch =
      !searchTerm ||
      lead.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      lead.primary_contact?.toLowerCase().includes(searchTerm.toLowerCase());

    return matchesSource && matchesPriority && matchesStatus && matchesSearch;
  });

  const getScoreColor = (score: number | undefined) => {
    if (!score) return 'text-gray-500';
    if (score >= 80) return 'text-green-600 dark:text-green-400';
    if (score >= 60) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  const getPriorityBadge = (priority: string | undefined) => {
    if (!priority) return null;
    const colors = {
      High: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300',
      Medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300',
      Low: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
    };
    return (
      <span
        className={`px-2 py-1 text-xs font-medium rounded-full ${
          colors[priority as keyof typeof colors] || 'bg-gray-100 text-gray-800'
        }`}
      >
        {priority}
      </span>
    );
  };

  const getSourceBadge = (source: string | undefined) => {
    if (!source) return null;
    const sourceLabels: Record<string, string> = {
      sniper: 'Sniper',
      web: 'Web',
      voice_call: 'Voice',
      google_ads: 'Google Ads',
      wordpress_form: 'WordPress',
    };
    return (
      <span className="px-2 py-1 text-xs font-medium rounded-full bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300">
        {sourceLabels[source] || source}
      </span>
    );
  };

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="text-center py-8 text-gray-600 dark:text-gray-400">Loading leads...</div>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Leads</h2>

        {/* Filters */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <Input
            label="Search"
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search by name or contact..."
          />
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Source
            </label>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-700 dark:text-white"
            >
              <option value="all">All Sources</option>
              <option value="sniper">Sniper</option>
              <option value="web">Web</option>
              <option value="voice_call">Voice</option>
              <option value="google_ads">Google Ads</option>
              <option value="wordpress_form">WordPress</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Priority
            </label>
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-700 dark:text-white"
            >
              <option value="all">All Priorities</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Status
            </label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-700 dark:text-white"
            >
              <option value="all">All Statuses</option>
              <option value="new">New</option>
              <option value="contacted">Contacted</option>
              <option value="called">Called</option>
              <option value="qualified">Qualified</option>
              <option value="won">Won</option>
              <option value="lost">Lost</option>
            </select>
          </div>
        </div>

        <div className="text-sm text-gray-600 dark:text-gray-400 mb-4">
          Showing {filteredLeads.length} of {leads.length} leads
        </div>
      </div>

      {filteredLeads.length === 0 ? (
        <div className="text-center py-8 text-gray-600 dark:text-gray-400">
          No leads found. {leads.length === 0 ? 'Start hunting to find leads!' : 'Try adjusting your filters.'}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Contact
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Score
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Source
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Priority
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Call Info
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {filteredLeads.map((lead) => (
                <tr key={lead.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900 dark:text-white">
                      {lead.name}
                    </div>
                    <div className="text-xs text-gray-400 dark:text-gray-500 font-mono mt-1">
                      ID: {lead.id}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {lead.primary_contact || '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`text-sm font-bold ${getScoreColor(lead.metadata?.score)}`}>
                      {lead.metadata?.score !== undefined ? lead.metadata.score : '-'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {getSourceBadge(lead.metadata?.source)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {getPriorityBadge(lead.metadata?.priority)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300">
                      {lead.metadata?.status || 'new'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {lead.metadata?.call_status ? (
                      <div className="flex flex-col gap-1">
                        <span className="text-xs">
                          {lead.metadata.call_status === 'completed' ? '✅ Called' : lead.metadata.call_status}
                        </span>
                        {lead.metadata.call_duration && (
                          <span className="text-xs text-gray-400">
                            {Math.floor(lead.metadata.call_duration / 60)}m {lead.metadata.call_duration % 60}s
                          </span>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <div className="flex gap-2">
                      <Button
                        variant="ghost"
                        onClick={() => {
                          setSelectedLead(lead);
                          setIsModalOpen(true);
                        }}
                        className="text-xs"
                      >
                        View Details
                      </Button>
                      {onTestCall && (
                        <Button
                          variant="ghost"
                          onClick={() => onTestCall(lead.id)}
                          className="text-xs"
                        >
                          Test Call
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Lead Details Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setSelectedLead(null);
        }}
        title={selectedLead ? `Lead Details: ${selectedLead.name}` : 'Lead Details'}
      >
        {selectedLead && (
          <div className="space-y-6">
            {/* Basic Information */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Basic Information</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Name</label>
                  <p className="text-sm text-gray-900 dark:text-white mt-1">{selectedLead.name}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Contact</label>
                  <p className="text-sm text-gray-900 dark:text-white mt-1">{selectedLead.primary_contact || '-'}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Lead ID</label>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 font-mono break-all">
                    {selectedLead.id}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Score</label>
                  <p className={`text-sm font-bold mt-1 ${getScoreColor(selectedLead.metadata?.score)}`}>
                    {selectedLead.metadata?.score !== undefined ? selectedLead.metadata.score : '-'}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Source</label>
                  <p className="text-sm text-gray-900 dark:text-white mt-1">
                    {getSourceBadge(selectedLead.metadata?.source)}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Priority</label>
                  <p className="text-sm text-gray-900 dark:text-white mt-1">
                    {getPriorityBadge(selectedLead.metadata?.priority)}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Status</label>
                  <p className="text-sm text-gray-900 dark:text-white mt-1">
                    <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300">
                      {selectedLead.metadata?.status || 'new'}
                    </span>
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Created At</label>
                  <p className="text-sm text-gray-900 dark:text-white mt-1">
                    {selectedLead.created_at
                      ? new Date(selectedLead.created_at).toLocaleString()
                      : '-'}
                  </p>
                </div>
              </div>
            </div>

            {/* Call Information */}
            {selectedLead.metadata?.call_status && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Call Information</h3>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Call Status</label>
                    <p className="text-sm text-gray-900 dark:text-white mt-1">
                      <span className="px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300">
                        {selectedLead.metadata.call_status}
                      </span>
                    </p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Call Duration</label>
                    <p className="text-sm text-gray-900 dark:text-white mt-1">
                      {selectedLead.metadata.call_duration
                        ? `${Math.floor(selectedLead.metadata.call_duration / 60)}m ${selectedLead.metadata.call_duration % 60}s`
                        : '-'}
                    </p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Called At</label>
                    <p className="text-sm text-gray-900 dark:text-white mt-1">
                      {selectedLead.metadata.called_at
                        ? new Date(selectedLead.metadata.called_at).toLocaleString()
                        : '-'}
                    </p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Call SID</label>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 font-mono text-xs">
                      {selectedLead.metadata.call_sid || '-'}
                    </p>
                  </div>
                </div>

                {/* Call Analysis (Gemini structured data) */}
                {selectedLead.metadata.call_analysis && (
                  <div className="mb-4">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Call Analysis</h3>
                    <div className="space-y-4">
                      {/* Summary */}
                      {selectedLead.metadata.call_analysis.summary && (
                        <div>
                          <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                            Summary
                          </label>
                          <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4">
                            <p className="text-sm text-gray-900 dark:text-white">
                              {selectedLead.metadata.call_analysis.summary}
                            </p>
                          </div>
                        </div>
                      )}

                      {/* Key Points */}
                      {selectedLead.metadata.call_analysis.key_points && (
                        <div>
                          <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                            Key Points
                          </label>
                          <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                            <ul className="list-disc list-inside space-y-1">
                              {Array.isArray(selectedLead.metadata.call_analysis.key_points) ? (
                                selectedLead.metadata.call_analysis.key_points.map((point: string, idx: number) => (
                                  <li key={idx} className="text-sm text-gray-900 dark:text-white">
                                    {point}
                                  </li>
                                ))
                              ) : (
                                <li className="text-sm text-gray-900 dark:text-white">
                                  {selectedLead.metadata.call_analysis.key_points}
                                </li>
                              )}
                            </ul>
                          </div>
                        </div>
                      )}

                      {/* Customer Intent & Next Steps */}
                      <div className="grid grid-cols-2 gap-4">
                        {selectedLead.metadata.call_analysis.customer_intent && (
                          <div>
                            <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                              Customer Intent
                            </label>
                            <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
                              <p className="text-sm text-gray-900 dark:text-white">
                                {selectedLead.metadata.call_analysis.customer_intent}
                              </p>
                            </div>
                          </div>
                        )}

                        {selectedLead.metadata.call_analysis.next_steps && (
                          <div>
                            <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                              Next Steps
                            </label>
                            <div className="bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-3">
                              <p className="text-sm text-gray-900 dark:text-white">
                                {Array.isArray(selectedLead.metadata.call_analysis.next_steps) 
                                  ? selectedLead.metadata.call_analysis.next_steps.join(', ')
                                  : selectedLead.metadata.call_analysis.next_steps}
                              </p>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Sentiment & Urgency */}
                      <div className="grid grid-cols-2 gap-4">
                        {selectedLead.metadata.call_analysis.sentiment && (
                          <div>
                            <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                              Sentiment
                            </label>
                            <span className={`px-3 py-1 text-xs font-medium rounded-full ${
                              selectedLead.metadata.call_analysis.sentiment === 'positive' 
                                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300'
                                : selectedLead.metadata.call_analysis.sentiment === 'negative'
                                ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300'
                                : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                            }`}>
                              {selectedLead.metadata.call_analysis.sentiment}
                            </span>
                          </div>
                        )}

                        {selectedLead.metadata.call_analysis.urgency && (
                          <div>
                            <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                              Urgency
                            </label>
                            <span className={`px-3 py-1 text-xs font-medium rounded-full ${
                              selectedLead.metadata.call_analysis.urgency === 'high' 
                                ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300'
                                : selectedLead.metadata.call_analysis.urgency === 'medium'
                                ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300'
                                : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300'
                            }`}>
                              {selectedLead.metadata.call_analysis.urgency}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* Full Transcription (collapsible) */}
                {selectedLead.metadata.call_transcription && (
                  <div>
                    <details className="mb-4">
                      <summary className="text-sm font-medium text-gray-700 dark:text-gray-300 cursor-pointer hover:text-gray-900 dark:hover:text-gray-100 mb-2">
                        Full Transcription
                      </summary>
                      <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 max-h-64 overflow-y-auto mt-2">
                        <p className="text-sm text-gray-900 dark:text-white whitespace-pre-wrap">
                          {selectedLead.metadata.call_transcription}
                        </p>
                      </div>
                    </details>
                  </div>
                )}

                {/* Recording URL (hidden, just for reference) */}
                {selectedLead.metadata.recording_url && (
                  <div className="mb-4">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                      Recording URL
                    </label>
                    <p className="text-xs text-gray-500 dark:text-gray-400 font-mono break-all">
                      {selectedLead.metadata.recording_url}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                      Note: Recording requires Twilio authentication to access
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Additional Metadata */}
            {selectedLead.metadata?.message && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Message</h3>
                <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                  <p className="text-sm text-gray-900 dark:text-white whitespace-pre-wrap">
                    {selectedLead.metadata.message}
                  </p>
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </Card>
  );
}
