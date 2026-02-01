// app/(dashboard)/dashboard/page.tsx
'use client';

import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { useProjectStore } from '@/lib/store';
import EmptyState from '@/components/dashboard/EmptyState';
import ProjectSelector from '@/components/dashboard/ProjectSelector';
import MetricCard from '@/components/dashboard/MetricCard';
import CampaignTable from '@/components/campaigns/CampaignTable';
import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import { useAuth } from '@/lib/hooks';

export default function DashboardPage() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const { setActiveProject, activeProjectId } = useProjectStore();

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await api.get('/api/projects');
      return response.data.projects || [];
    },
  });

  const projectId = activeProjectId ?? projects?.[0]?.project_id;
  const { data: campaigns = [] } = useQuery({
    queryKey: ['campaigns', projectId],
    queryFn: async () => {
      if (!projectId) return [];
      const response = await api.get(`/api/projects/${projectId}/campaigns`);
      return response.data.campaigns || [];
    },
    enabled: !!projectId,
  });

  const handleCreateProject = () => {
    router.push('/onboarding');
  };

  const handleProjectClick = (projectId: string) => {
    setActiveProject(projectId);
    router.push(`/projects/${projectId}`);
  };

  const campaignRows = campaigns.map((c: { id: string; name?: string; module?: string; status?: string }) => ({
    id: c.id,
    name: c.name ?? c.id,
    module: c.module ?? '—',
    status: c.status ?? 'DRAFT',
  }));

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-muted-foreground">Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <h1 className="text-2xl font-bold text-foreground">Apex OS</h1>
              {projects && projects.length > 0 && <ProjectSelector />}
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-muted-foreground">{user?.id}</span>
              <Button variant="ghost" onClick={logout}>
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {!projects || projects.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="space-y-8">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-foreground">Mission Control</h2>
              <div className="flex gap-2">
                <Button variant="secondary" onClick={handleCreateProject}>
                  New Project
                </Button>
                <Button onClick={() => router.push(projectId ? `/campaigns/new?projectId=${projectId}` : '/campaigns/new')}>
                  New Campaign
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard title="Leads Today" value={0} />
              <MetricCard title="Budget Used" value="$0" />
              <MetricCard title="Active Campaigns" value={campaignRows.length} />
              <MetricCard title="Projects" value={projects?.length ?? 0} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <h3 className="text-lg font-medium text-foreground mb-4">Your Projects</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {projects.map((project: { project_id: string; niche?: string; created_at?: string }) => (
                    <Card
                      key={project.project_id}
                      className="cursor-pointer hover:border-primary/50 transition-colors"
                      onClick={() => handleProjectClick(project.project_id)}
                    >
                      <h3 className="font-semibold text-foreground mb-1">
                        {project.niche || project.project_id}
                      </h3>
                      <p className="text-sm text-muted-foreground">
                        {project.project_id}
                      </p>
                      {project.created_at && (
                        <p className="text-xs text-muted-foreground mt-2">
                          {new Date(project.created_at).toLocaleDateString()}
                        </p>
                      )}
                    </Card>
                  ))}
                </div>
              </div>
              <div>
                <h3 className="text-lg font-medium text-foreground mb-4">Campaigns</h3>
                {campaignRows.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No campaigns yet. Create one to get started.</p>
                ) : (
                  <CampaignTable campaigns={campaignRows} />
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
