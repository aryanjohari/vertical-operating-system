// app/(dashboard)/system/page.tsx
'use client';

import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getSystemHealth, getSystemLogs, getUsageRecords, SystemHealth, SystemLogs, UsageResponse } from '@/lib/api';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';

export default function SystemPage() {
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [logLines, setLogLines] = useState(50);

  // Health status query
  const { data: health, refetch: refetchHealth } = useQuery<SystemHealth>({
    queryKey: ['system-health'],
    queryFn: getSystemHealth,
    refetchInterval: autoRefresh ? 30000 : false, // Auto-refresh every 30 seconds
  });

  // Logs query
  const { data: logs, refetch: refetchLogs } = useQuery<SystemLogs>({
    queryKey: ['system-logs', logLines],
    queryFn: () => getSystemLogs(logLines),
    refetchInterval: autoRefresh ? 5000 : false, // Auto-refresh every 5 seconds
  });

  // Usage records query
  const { data: usage, refetch: refetchUsage } = useQuery<UsageResponse>({
    queryKey: ['system-usage'],
    queryFn: () => getUsageRecords(undefined, 100),
    refetchInterval: autoRefresh ? 30000 : false, // Auto-refresh every 30 seconds
  });

  // Auto-scroll logs to bottom
  useEffect(() => {
    if (logs?.logs) {
      const logContainer = document.getElementById('log-viewer');
      if (logContainer) {
        logContainer.scrollTop = logContainer.scrollHeight;
      }
    }
  }, [logs]);

  const StatusIndicator = ({ status }: { status: boolean }) => (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
      status 
        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' 
        : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
    }`}>
      {status ? '✓ OK' : '✗ Failed'}
    </span>
  );

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              System Dashboard
            </h1>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="rounded"
                />
                Auto-refresh
              </label>
              <Button
                variant="ghost"
                onClick={() => {
                  refetchHealth();
                  refetchLogs();
                  refetchUsage();
                }}
              >
                Refresh All
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Health Cards */}
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            System Health
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    System Status
                  </p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                    {health?.status || 'Loading...'}
                  </p>
                </div>
                <StatusIndicator status={health?.status === 'online'} />
              </div>
            </Card>

            <Card>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    Redis
                  </p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                    {health?.redis_ok ? 'Online' : 'Offline'}
                  </p>
                </div>
                <StatusIndicator status={health?.redis_ok || false} />
              </div>
            </Card>

            <Card>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    Database
                  </p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                    {health?.database_ok ? 'Online' : 'Offline'}
                  </p>
                </div>
                <StatusIndicator status={health?.database_ok || false} />
              </div>
            </Card>

            <Card>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    Twilio
                  </p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                    {health?.twilio_ok ? 'Configured' : 'Not Configured'}
                  </p>
                </div>
                <StatusIndicator status={health?.twilio_ok || false} />
              </div>
            </Card>
          </div>

          {health && (
            <div className="mt-4">
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Loaded Agents: {health.loaded_agents?.length || 0} | 
                Version: {health.version} | 
                System: {health.system}
              </p>
            </div>
          )}
        </div>

        {/* Log Viewer */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              System Logs
            </h2>
            <div className="flex items-center gap-4">
              <select
                value={logLines}
                onChange={(e) => setLogLines(Number(e.target.value))}
                className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm"
              >
                <option value={25}>25 lines</option>
                <option value={50}>50 lines</option>
                <option value={100}>100 lines</option>
                <option value={200}>200 lines</option>
              </select>
              <Button variant="ghost" onClick={() => refetchLogs()}>
                Refresh Logs
              </Button>
            </div>
          </div>
          <Card>
            <div
              id="log-viewer"
              className="h-96 overflow-y-auto bg-gray-900 text-green-400 p-4 rounded font-mono text-xs"
              style={{ fontFamily: 'monospace' }}
            >
              {logs?.logs && logs.logs.length > 0 ? (
                logs.logs.map((line, index) => (
                  <div key={index} className="mb-1">
                    {line}
                  </div>
                ))
              ) : logs?.message ? (
                <div className="text-yellow-400">{logs.message}</div>
              ) : (
                <div className="text-gray-500">Loading logs...</div>
              )}
            </div>
            {logs && (
              <div className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                Showing {logs.total_lines} line{logs.total_lines !== 1 ? 's' : ''}
              </div>
            )}
          </Card>
        </div>

        {/* Billing Table */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              Usage & Billing
            </h2>
            <Button variant="ghost" onClick={() => refetchUsage()}>
              Refresh Usage
            </Button>
          </div>
          <Card>
            {usage && usage.usage.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead className="bg-gray-50 dark:bg-gray-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        Timestamp
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        Project ID
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        Resource Type
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        Quantity
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        Cost (USD)
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                    {usage.usage.map((record) => (
                      <tr key={record.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                          {new Date(record.timestamp).toLocaleString()}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                          {record.project_id}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                          {record.resource_type}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                          {record.quantity.toFixed(2)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                          ${record.cost_usd.toFixed(4)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="mt-4 text-sm text-gray-600 dark:text-gray-400">
                  Total records: {usage.total}
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                No usage records found
              </div>
            )}
          </Card>
        </div>
      </main>
    </div>
  );
}
