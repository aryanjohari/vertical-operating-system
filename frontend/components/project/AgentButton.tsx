// components/project/AgentButton.tsx
'use client';

import { useState } from 'react';
import api, { isHeavyTask, pollContextUntilComplete } from '@/lib/api';
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

      // Handle async response (processing status)
      if (response.data.status === 'processing') {
        const contextId = response.data.data?.context_id;
        if (contextId) {
          try {
            // Poll for completion
            const result = await pollContextUntilComplete(contextId);
            if (result && (result.status === 'success' || result.status === 'complete')) {
              updateLastRunTime(agentKey);
              // Add small delay to ensure DB writes are committed
              await new Promise(resolve => setTimeout(resolve, 500));
              if (onComplete) {
                onComplete();
              }
            } else {
              console.error(`Task ${agentKey} completed with status:`, result?.status);
            }
          } catch (error) {
            console.error(`Error polling context for ${agentKey}:`, error);
            // Show error to user - task may have failed or timed out
          }
        }
      } else if (response.data.status === 'success' || response.data.status === 'complete') {
        // Sync task completed immediately
        updateLastRunTime(agentKey);
        // Add small delay to ensure DB writes are committed
        await new Promise(resolve => setTimeout(resolve, 500));
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
