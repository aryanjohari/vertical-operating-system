# Frontend Migration Guide - Titanium Upgrade

**Version:** 3.0 (Titanium Kernel)  
**Target Audience:** Frontend Developers  
**Purpose:** Guide for migrating frontend code to support async task execution and new response formats

---

## Executive Summary

The backend has been upgraded to support **asynchronous task execution** for heavy operations. This means:

1. **Heavy tasks** (sniper_agent, sales_agent, reactivator_agent, onboarding) now return immediately with `status: "processing"` and a `context_id`
2. **Light tasks** continue to work synchronously (no breaking changes)
3. **Frontend must handle** the new `"processing"` status and implement polling/webhooks for task completion

---

## Breaking Changes

### 1. `/api/run` Response Format Change

**Before (Synchronous):**
```typescript
// All tasks returned final result immediately
{
  status: "success" | "error" | "complete",
  data: { ... },
  message: "Task completed",
  timestamp: "2024-01-01T00:00:00"
}
```

**After (Asynchronous for Heavy Tasks):**
```typescript
// Heavy tasks return immediately with processing status
{
  status: "processing",  // ⚠️ NEW STATUS
  data: {
    context_id: "uuid-here",  // ⚠️ NEW FIELD
    task: "sniper_agent"
  },
  message: "Task 'sniper_agent' is processing in background",
  timestamp: "2024-01-01T00:00:00"
}
```

**Affected Tasks:**
- `sniper_agent` - Now async
- `sales_agent` - Now async
- `reactivator_agent` - Now async
- `onboarding` - Now async

**Unaffected Tasks (Still Sync):**
- `manager` (with `action: "dashboard_stats"`)
- `lead_gen_manager` (with `action: "dashboard_stats"`)
- `health_check`
- All other quick operations

---

## Components Requiring Updates

### 1. `components/project/AgentButton.tsx`

**Current Behavior:**
- Expects `status === 'success'` or `status === 'complete'` immediately
- Sets loading state to false after response
- Calls `onComplete()` callback immediately

**Required Changes:**
```typescript
// Add check for async tasks
const HEAVY_TASKS = ['sniper_agent', 'sales_agent', 'reactivator_agent', 'onboarding'];
const isHeavyTask = HEAVY_TASKS.includes(agentKey);

const handleClick = async () => {
  // ... existing code ...
  
  try {
    const response = await api.post('/api/run', { ... });
    
    // Handle async response
    if (response.data.status === 'processing') {
      const contextId = response.data.data.context_id;
      
      // Start polling for completion
      await pollContextUntilComplete(contextId);
      
      // Then proceed with success handling
      updateLastRunTime(agentKey);
      if (onComplete) onComplete();
    } else if (response.data.status === 'success' || response.data.status === 'complete') {
      // Sync task completed immediately
      updateLastRunTime(agentKey);
      if (onComplete) onComplete();
    }
  } catch (error) {
    // ... error handling ...
  } finally {
    setIsLoading(false);
    setRunning(false);
  }
};
```

**New UI States Needed:**
- "Processing..." state (different from "Loading...")
- Progress indicator for long-running tasks
- Option to cancel/stop task (future enhancement)

---

### 2. `components/leadgen/LeadGenActions.tsx`

**Current Behavior:**
- `hunt_sniper` action expects immediate success
- `ignite_reactivation` action expects immediate success
- `instant_call` action expects immediate success

**Required Changes:**
```typescript
const handleAction = async (action: string, additionalParams: Record<string, any> = {}) => {
  // ... existing code ...
  
  try {
    const response = await api.post('/api/run', {
      task: 'lead_gen_manager',
      params: {
        project_id: projectId,
        action: action,
        ...additionalParams,
      },
    });

    // Handle async response
    if (response.data.status === 'processing') {
      const contextId = response.data.data.context_id;
      
      // Show processing state
      setIsLoading(action);
      
      // Poll for completion
      await pollContextUntilComplete(contextId);
      
      // Then proceed with success handling
      updateLastRunTime(`lead_gen_${action}`);
      if (onComplete) onComplete();
    } else if (response.data.status === 'success' || response.data.status === 'complete') {
      // Sync action completed immediately
      updateLastRunTime(`lead_gen_${action}`);
      if (onComplete) onComplete();
    } else {
      console.error(`Error running ${action}:`, response.data.message);
    }
  } catch (error) {
    // ... error handling ...
  } finally {
    setIsLoading(null);
    setRunning(false);
  }
};
```

**New UI States Needed:**
- "Hunting leads..." (for hunt_sniper)
- "Sending SMS..." (for ignite_reactivation)
- "Connecting call..." (for instant_call)

---

### 3. `app/(dashboard)/onboarding/page.tsx`

**Current Behavior:**
- `onboarding` task expects immediate completion
- Shows loading spinner during execution

**Required Changes:**
```typescript
// Onboarding is now async - must handle processing status
const response = await api.post('/api/run', {
  task: 'onboarding',
  params: { ... }
});

if (response.data.status === 'processing') {
  const contextId = response.data.data.context_id;
  
  // Show "Generating DNA..." message
  setStatus('Generating your project DNA...');
  
  // Poll for completion
  await pollContextUntilComplete(contextId);
  
  // Navigate to project dashboard
  router.push(`/projects/${projectId}`);
}
```

**New UI States Needed:**
- "Generating DNA..." (instead of just "Loading...")
- Progress steps: "Analyzing website...", "Creating profile...", "Finalizing..."

---

### 4. `components/onboarding/InterviewChat.tsx`

**Current Behavior:**
- Multiple `/api/run` calls for onboarding steps
- Expects immediate responses

**Required Changes:**
- Same as above - handle `processing` status
- Show appropriate progress messages for each step

---

### 5. `app/(dashboard)/projects/[id]/page.tsx`

**Status:** ✅ **NO CHANGES NEEDED**
- Uses `manager` with `action: "dashboard_stats"` (light task, still sync)
- Already handles response correctly

---

### 6. `app/(dashboard)/projects/[id]/lead-gen/page.tsx`

**Current Behavior:**
- Calls `lead_gen_manager` with `action: "dashboard_stats"` (sync, OK)
- Also has action buttons that may trigger async tasks

**Required Changes:**
- Only update action buttons (hunt_sniper, etc.) - same as `LeadGenActions.tsx`

---

## TypeScript Interface Updates

### Update `lib/types.ts`

**Add New Types:**
```typescript
// Add to existing AgentOutput interface
export interface AgentOutput {
  status: 'success' | 'error' | 'complete' | 'warning' | 'skipped' | 'processing';  // ⚠️ ADD 'processing'
  data: any;
  message: string;
  timestamp: string;
  error_details?: any;
  context_id?: string;  // ⚠️ ADD optional context_id
}

// New interface for processing response
export interface ProcessingResponse {
  status: 'processing';
  data: {
    context_id: string;
    task: string;
  };
  message: string;
  timestamp: string;
}

// New interface for context polling
export interface AgentContext {
  context_id: string;
  project_id: string;
  user_id: string;
  created_at: string;
  expires_at: string;
  data: {
    request_id?: string;
    task?: string;
    status?: 'processing' | 'completed' | 'failed';
    result?: AgentOutput;
  };
}
```

---

## New API Endpoints Needed

### 1. GET `/api/context/{context_id}`

**Purpose:** Poll context status for async task completion

**Response:**
```json
{
  "context_id": "uuid",
  "project_id": "apex-bail-manukau",
  "user_id": "user@example.com",
  "created_at": "2024-01-01T00:00:00",
  "expires_at": "2024-01-01T01:00:00",
  "data": {
    "request_id": "uuid",
    "task": "sniper_agent",
    "status": "processing" | "completed" | "failed",
    "result": {
      "status": "success",
      "data": { ... },
      "message": "Task completed"
    }
  }
}
```

**Implementation Required:**
- Backend must store task results in context.data.result
- Frontend polls this endpoint every 2-3 seconds until status === "completed"

---

## Helper Functions to Add

### 1. Context Polling Utility

**File:** `lib/api.ts` or `lib/utils.ts`

```typescript
/**
 * Polls context until task completes or times out
 * @param contextId - Context ID from processing response
 * @param maxAttempts - Maximum polling attempts (default: 60 = 2 minutes at 2s interval)
 * @param intervalMs - Polling interval in milliseconds (default: 2000)
 * @returns Final AgentOutput or null if timeout
 */
export async function pollContextUntilComplete(
  contextId: string,
  maxAttempts: number = 60,
  intervalMs: number = 2000
): Promise<AgentOutput | null> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      const response = await api.get(`/api/context/${contextId}`);
      const context = response.data;
      
      if (context.data.status === 'completed') {
        return context.data.result;
      } else if (context.data.status === 'failed') {
        throw new Error(context.data.result?.message || 'Task failed');
      }
      
      // Still processing, wait and retry
      await new Promise(resolve => setTimeout(resolve, intervalMs));
    } catch (error) {
      // If context not found (expired), return null
      if (error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  }
  
  // Timeout
  throw new Error('Task timeout: Context polling exceeded max attempts');
}
```

### 2. Task Classification Helper

**File:** `lib/utils.ts`

```typescript
/**
 * Determines if a task is heavy (async) or light (sync)
 */
export const HEAVY_TASKS = [
  'sniper_agent',
  'sales_agent',
  'reactivator_agent',
  'onboarding'
];

export function isHeavyTask(task: string): boolean {
  return HEAVY_TASKS.includes(task);
}
```

---

## New UI States & Components

### 1. Processing State Indicator

**Component:** `components/ui/ProcessingIndicator.tsx`

```typescript
interface ProcessingIndicatorProps {
  task: string;
  contextId?: string;
  onCancel?: () => void;
}

export default function ProcessingIndicator({ task, contextId, onCancel }: ProcessingIndicatorProps) {
  const taskLabels: Record<string, string> = {
    'sniper_agent': 'Hunting leads...',
    'sales_agent': 'Connecting call...',
    'reactivator_agent': 'Sending SMS...',
    'onboarding': 'Generating DNA...'
  };
  
  return (
    <div className="flex items-center gap-2 text-blue-600">
      <Spinner />
      <span>{taskLabels[task] || 'Processing...'}</span>
      {onCancel && (
        <Button variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
      )}
    </div>
  );
}
```

### 2. Project Status Badge

**New State:** "PAUSED" (when spending limit exceeded)

**Component Update:** `components/project/ProjectStatus.tsx`

```typescript
// Add new status type
type ProjectStatus = 'active' | 'paused' | 'error';

// Show paused state when AccountantAgent returns status: "PAUSED"
if (billingStatus === 'PAUSED') {
  return (
    <Badge variant="warning">
      Project Paused - Spending Limit Exceeded
    </Badge>
  );
}
```

---

## Migration Checklist

### Phase 1: Type Updates
- [ ] Update `AgentOutput` interface to include `'processing'` status
- [ ] Add `context_id` to `AgentOutput` interface
- [ ] Create `ProcessingResponse` interface
- [ ] Create `AgentContext` interface

### Phase 2: API Utilities
- [ ] Implement `pollContextUntilComplete()` helper
- [ ] Implement `isHeavyTask()` helper
- [ ] Add GET `/api/context/{context_id}` endpoint (backend)

### Phase 3: Component Updates
- [ ] Update `AgentButton.tsx` to handle async tasks
- [ ] Update `LeadGenActions.tsx` to handle async tasks
- [ ] Update `onboarding/page.tsx` to handle async onboarding
- [ ] Update `InterviewChat.tsx` to handle async steps
- [ ] Update `lead-gen/page.tsx` action buttons

### Phase 4: UI Components
- [ ] Create `ProcessingIndicator.tsx` component
- [ ] Add "PAUSED" status to `ProjectStatus.tsx`
- [ ] Add loading states for each heavy task type
- [ ] Add error handling for context polling failures

### Phase 5: Testing
- [ ] Test `sniper_agent` async flow
- [ ] Test `sales_agent` async flow
- [ ] Test `reactivator_agent` async flow
- [ ] Test `onboarding` async flow
- [ ] Test context polling timeout scenarios
- [ ] Test sync tasks still work (manager, dashboard_stats)

---

## Backward Compatibility Notes

### What Still Works (No Changes)
- ✅ `manager` with `action: "dashboard_stats"` - Still sync
- ✅ `lead_gen_manager` with `action: "dashboard_stats"` - Still sync
- ✅ `health_check` - Still sync
- ✅ All entity CRUD operations
- ✅ All authentication flows

### What Breaks (Requires Updates)
- ❌ `sniper_agent` - Now async, must handle `processing` status
- ❌ `sales_agent` - Now async, must handle `processing` status
- ❌ `reactivator_agent` - Now async, must handle `processing` status
- ❌ `onboarding` - Now async, must handle `processing` status

---

## Example Migration: AgentButton.tsx

**Before:**
```typescript
const response = await api.post('/api/run', { ... });

if (response.data.status === 'success' || response.data.status === 'complete') {
  updateLastRunTime(agentKey);
  if (onComplete) onComplete();
}
```

**After:**
```typescript
const response = await api.post('/api/run', { ... });

if (response.data.status === 'processing') {
  // Async task - poll for completion
  const contextId = response.data.data.context_id;
  try {
    const result = await pollContextUntilComplete(contextId);
    if (result && (result.status === 'success' || result.status === 'complete')) {
      updateLastRunTime(agentKey);
      if (onComplete) onComplete();
    }
  } catch (error) {
    console.error('Task failed or timed out:', error);
    // Show error to user
  }
} else if (response.data.status === 'success' || response.data.status === 'complete') {
  // Sync task - immediate completion
  updateLastRunTime(agentKey);
  if (onComplete) onComplete();
}
```

---

## Support & Questions

For questions or issues during migration:
1. Check backend logs for context creation/updates
2. Verify Redis is running (or in-memory fallback is working)
3. Test with light tasks first (manager, dashboard_stats)
4. Check context TTL (default: 3600 seconds)

---

**Document Version:** 1.0  
**Last Updated:** 2024  
**Maintained By:** Engineering Team
