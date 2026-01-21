// components/dashboard/ProjectSelector.tsx
'use client';

import { useRouter } from 'next/navigation';
import { useProjectStore } from '@/lib/store';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { Project } from '@/lib/types';

export default function ProjectSelector() {
  const router = useRouter();
  const { activeProjectId, setActiveProject, projects, setProjects } = useProjectStore();

  const { data, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await api.get('/api/projects');
      const projects = response.data.projects || [];
      setProjects(projects);
      return projects;
    },
  });

  const handleProjectChange = (projectId: string) => {
    setActiveProject(projectId);
    router.push(`/projects/${projectId}`);
  };

  if (isLoading) {
    return (
      <select className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white">
        <option>Loading...</option>
      </select>
    );
  }

  if (!data || data.length === 0) {
    return null;
  }

  return (
    <select
      value={activeProjectId || ''}
      onChange={(e) => handleProjectChange(e.target.value)}
      className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
    >
      <option value="">Select a project...</option>
      {data.map((project: Project) => (
        <option key={project.project_id} value={project.project_id}>
          {project.niche || project.project_id}
        </option>
      ))}
    </select>
  );
}
