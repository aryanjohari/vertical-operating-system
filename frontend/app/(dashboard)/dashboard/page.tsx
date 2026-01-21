// app/(dashboard)/dashboard/page.tsx
'use client';

import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { useProjectStore } from '@/lib/store';
import EmptyState from '@/components/dashboard/EmptyState';
import ProjectSelector from '@/components/dashboard/ProjectSelector';
import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import { useAuth } from '@/lib/hooks';

export default function DashboardPage() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const { setActiveProject } = useProjectStore();

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await api.get('/api/projects');
      return response.data.projects || [];
    },
  });

  const handleCreateProject = () => {
    router.push('/onboarding');
  };

  const handleProjectClick = (projectId: string) => {
    setActiveProject(projectId);
    router.push(`/projects/${projectId}`);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center">Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                Apex OS
              </h1>
              {projects && projects.length > 0 && <ProjectSelector />}
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {user?.id}
              </span>
              <Button variant="ghost" onClick={logout}>
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {!projects || projects.length === 0 ? (
          <EmptyState />
        ) : (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                Your Projects
              </h2>
              <Button onClick={handleCreateProject}>Create New Project</Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {projects.map((project: any) => (
                <Card
                  key={project.project_id}
                  className="cursor-pointer hover:shadow-lg transition-shadow"
                  onClick={() => handleProjectClick(project.project_id)}
                >
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                    {project.niche || project.project_id}
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Project ID: {project.project_id}
                  </p>
                  {project.created_at && (
                    <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">
                      Created: {new Date(project.created_at).toLocaleDateString()}
                    </p>
                  )}
                </Card>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
