// components/project/AgentButton.tsx
'use client';

import { useState } from 'react';
import api from '@/lib/api';
import { useAgentStore } from '@/lib/store';
import Button from '@/components/ui/Button';

interface AgentButtonProps {
  agentKey: string;
  label: string;
  projectId: string;
  onComplete?: () => void;
  disabled?: boolean;
}

export default function AgentButton({
  agentKey,
  label,
  projectId,
  onComplete,
  disabled = false,
}: AgentButtonProps) {
  const { isRunning, runningAgent, setRunning, updateLastRunTime } = useAgentStore();
  const [isLoading, setIsLoading] = useState(false);

  const isDisabled = disabled || isRunning || isLoading;
  const isCurrentlyRunning = runningAgent === agentKey;

  const handleClick = async () => {
    if (isDisabled) return;

    setIsLoading(true);
    setRunning(true, agentKey);

    try {
      const response = await api.post('/api/run', {
        task: agentKey,
        user_id: '', // Will be set by backend
        params: {
          project_id: projectId,
        },
      });

      if (response.data.status === 'success' || response.data.status === 'complete') {
        updateLastRunTime(agentKey);
        if (onComplete) {
          onComplete();
        }
      }
    } catch (error) {
      console.error(`Error running ${agentKey}:`, error);
    } finally {
      setIsLoading(false);
      setRunning(false);
    }
  };

  return (
    <Button
      onClick={handleClick}
      disabled={isDisabled}
      isLoading={isLoading || isCurrentlyRunning}
      variant={isCurrentlyRunning ? 'primary' : 'secondary'}
      className="w-full"
    >
      {isCurrentlyRunning ? 'Running...' : `Run ${label}`}
    </Button>
  );
}
