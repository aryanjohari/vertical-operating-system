// app/(dashboard)/projects/[id]/lead-gen/page.tsx
'use client';

import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import api, { pollContextUntilComplete } from '@/lib/api';
import { LeadGenStats } from '@/lib/types';
import LeadGenDashboard from '@/components/leadgen/LeadGenDashboard';
import LeadGenActions from '@/components/leadgen/LeadGenActions';
import LeadsList from '@/components/leadgen/LeadsList';

export default function LeadGenPage() {
  const params = useParams();
  const projectId = params.id as string;

  const { data: managerData, refetch, isLoading } = useQuery({
    queryKey: ['lead-gen-stats', projectId],
    queryFn: async () => {
      const response = await api.post('/api/run', {
        task: 'lead_gen_manager',
        user_id: '',
        params: {
          project_id: projectId,
          action: 'dashboard_stats',
        },
      });

      if (response.data.status === 'success' && response.data.data) {
        return response.data.data as LeadGenStats;
      }
      return null;
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const stats: LeadGenStats = managerData || {
    total_leads: 0,
    avg_lead_score: 0,
    total_pipeline_value: 0,
    conversion_rate: 0,
    sources: {
      sniper: 0,
      web: 0,
      voice: 0,
      google_ads: 0,
      wordpress_form: 0,
    },
    priorities: {
      high: 0,
      medium: 0,
      low: 0,
    },
    recent_leads: [],
  };

  const handleTestCall = async (leadId: string) => {
    try {
      const response = await api.post('/api/run', {
        task: 'lead_gen_manager',
        user_id: '',
        params: {
          project_id: projectId,
          action: 'instant_call',
          lead_id: leadId,
        },
      });

      // Handle async response (instant_call is now async)
      if (response.data.status === 'processing') {
        const contextId = response.data.data?.context_id;
        if (contextId) {
          alert('Call is being initiated...');
          try {
            // Poll for completion
            const result = await pollContextUntilComplete(contextId);
            if (result && result.status === 'success') {
              alert('Call initiated successfully!');
              refetch();
            } else {
              alert(`Error: ${result?.message || 'Failed to initiate call'}`);
            }
          } catch (error: any) {
            console.error('Error polling context:', error);
            alert('Call initiation timed out or failed. Please try again.');
          }
        } else {
          alert('Error: No context ID received');
        }
      } else if (response.data.status === 'success') {
        // Sync completion (shouldn't happen, but handle it)
        alert('Call initiated successfully!');
        refetch();
      } else {
        alert(`Error: ${response.data.message || 'Failed to initiate call'}`);
      }
    } catch (error) {
      console.error('Error initiating call:', error);
      alert('Failed to initiate call. Please try again.');
    }
  };

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="text-center">Loading lead gen dashboard...</div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          Lead Gen Dashboard
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Monitor and control your lead generation pipeline
        </p>
      </div>

      <div className="space-y-6">
        <LeadGenDashboard stats={stats} />
        
        <LeadGenActions projectId={projectId} onComplete={() => refetch()} />
        
        <LeadsList projectId={projectId} onTestCall={handleTestCall} />
      </div>
    </div>
  );
}
