// components/onboarding/InterviewChat.tsx
'use client';

import { useState, useEffect, useRef } from 'react';
import api from '@/lib/api';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';

interface InterviewChatProps {
  url: string;
  identityData: any;
  onComplete: (projectId: string) => void;
}

interface Message {
  role: 'assistant' | 'user';
  content: string;
}

export default function InterviewChat({ url, identityData, onComplete }: InterviewChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStarting, setIsStarting] = useState(true);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [context, setContext] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Start interview
    const startInterview = async () => {
      setIsLoading(true);
      try {
        // Extract identity from nested structure if needed
        const identity = identityData?.identity || identityData;
        
        const response = await api.post('/api/run', {
          task: 'onboarding',
          user_id: '',
          params: {
            step: 'interview_start',
            url,
            identity: identity,
            modules: ['local_seo'], // Only pSEO for now
            history: '',
            context: '',
          },
        });

        if ((response.data.status === 'success' || response.data.status === 'continue') && response.data.data) {
          const question = response.data.data.reply || response.data.data.question || response.data.message;
          setMessages([
            {
              role: 'assistant',
              content: question || 'Let me ask you a few questions to understand your business better.',
            },
          ]);
          // Store context for subsequent requests
          if (response.data.data.context) {
            setContext(response.data.data.context);
          }
          setIsStarting(false);
        }
      } catch (err: any) {
        setMessages([
          {
            role: 'assistant',
            content: 'Error starting interview. Please try again.',
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    };

    if (isStarting && identityData) {
      startInterview();
    }
  }, [url, identityData, isStarting]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      const history = messages
        .map((m) => `${m.role === 'user' ? 'User' : 'Assistant'}: ${m.content}`)
        .join('\n');

      // Extract identity from nested structure if needed
      const identity = identityData?.identity || identityData;
      
      const response = await api.post('/api/run', {
        task: 'onboarding',
        user_id: '',
        params: {
          step: 'interview_loop',
          url,
          identity: identity,
          modules: ['local_seo'],
          history: history + `\nUser: ${userMessage}`,
          context: context || {},
        },
      });

      if (response.data.status === 'success' || response.data.status === 'continue' || response.data.status === 'complete') {
        const assistantMessage = response.data.data?.reply || response.data.data?.question || response.data.message;
        
        if (response.data.status === 'complete' || response.data.data?.complete || response.data.data?.project_id) {
          // Interview complete, project created by onboarding agent
          // Extract project_id from path (format: "data/profiles/{project_id}")
          let newProjectId = response.data.data?.project_id;
          if (!newProjectId && response.data.data?.path) {
            const pathParts = response.data.data.path.split('/');
            newProjectId = pathParts[pathParts.length - 1]; // Get last part of path
          }
          if (!newProjectId) {
            newProjectId = response.data.data?.identity?.project_id;
          }
          if (newProjectId) {
            setProjectId(newProjectId);
            setMessages((prev) => [
              ...prev,
              {
                role: 'assistant',
                content: 'Great! I have all the information I need. Your project has been created!',
              },
            ]);
            
            // Wait a moment then redirect
            setTimeout(() => {
              onComplete(newProjectId);
            }, 2000);
          } else {
            setMessages((prev) => [
              ...prev,
              { role: 'assistant', content: 'Project creation in progress...' },
            ]);
          }
        } else {
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: assistantMessage },
          ]);
          // Update context if provided in response
          if (response.data.data?.context) {
            setContext(response.data.data.context);
          }
        }
      } else {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: 'Error processing response. Please try again.' },
        ]);
      }
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Error sending message. Please try again.' },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  if (isStarting) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Starting interview...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[500px]">
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50 dark:bg-gray-800 rounded-lg mb-4">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${
              message.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${
                message.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white'
              }`}
            >
              {message.content}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white dark:bg-gray-700 rounded-lg px-4 py-2">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Type your answer..."
          className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={isLoading || !!projectId}
        />
        <Button onClick={handleSend} disabled={isLoading || !!projectId}>
          Send
        </Button>
      </div>
    </div>
  );
}
