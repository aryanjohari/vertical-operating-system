// components/onboarding/CampaignCreator.tsx
"use client";

import { useState, useEffect, useRef } from "react";
import api from "@/lib/api";
import Button from "@/components/ui/Button";

interface CampaignCreatorProps {
  projectId: string;
  module: "pseo" | "lead_gen";
  moduleName: string;
  onComplete: (campaignId: string) => void;
  onSkip?: () => void;
}

interface Message {
  role: "assistant" | "user";
  content: string;
}

export default function CampaignCreator({
  projectId,
  module,
  moduleName,
  onComplete,
  onSkip,
}: CampaignCreatorProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isStarting, setIsStarting] = useState(true);
  const [campaignId, setCampaignId] = useState<string | null>(null);
  const [context, setContext] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Start campaign creation interview
    const startCampaignCreation = async () => {
      setIsLoading(true);
      try {
        const response = await api.post("/api/run", {
          task: "onboarding",
          user_id: "",
          params: {
            action: "create_campaign",
            project_id: projectId,
            module: module,
            name: `${moduleName} Campaign`,
            step: "interview_start",
            history: "",
            context: "",
          },
        });

        if (
          response.data.status === "continue" ||
          response.data.status === "success"
        ) {
          const question =
            response.data.data?.reply ||
            response.data.data?.question ||
            response.data.message ||
            `Let me ask you a few questions to configure your ${moduleName} campaign.`;
          setMessages([
            {
              role: "assistant",
              content: question,
            },
          ]);
          if (response.data.data?.context) {
            setContext(response.data.data.context);
          }
          setIsStarting(false);
        } else if (response.data.status === "error") {
          setMessages([
            {
              role: "assistant",
              content: `Error: ${response.data.message || "Failed to start campaign creation"}`,
            },
          ]);
          setIsStarting(false);
        }
      } catch (err: any) {
        setMessages([
          {
            role: "assistant",
            content: "Error starting campaign creation. Please try again.",
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    };

    if (isStarting) {
      startCampaignCreation();
    }
  }, [projectId, module, moduleName, isStarting]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    try {
      const history = messages
        .map((m) => `${m.role === "user" ? "User" : "Assistant"}: ${m.content}`)
        .join("\n");

      const response = await api.post("/api/run", {
        task: "onboarding",
        user_id: "",
        params: {
          action: "create_campaign",
          project_id: projectId,
          module: module,
          step: "interview_loop",
          history: history + `\nUser: ${userMessage}`,
          context: context || {},
        },
      });

      if (response.data.status === "complete") {
        // Campaign creation complete
        const newCampaignId = response.data.data?.campaign_id;
        if (newCampaignId) {
          setCampaignId(newCampaignId);
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: `Great! Your ${moduleName} campaign has been created successfully!`,
            },
          ]);

          setTimeout(() => {
            onComplete(newCampaignId);
          }, 2000);
        } else {
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content:
                "Campaign creation completed but no campaign ID received. Please check your campaigns.",
            },
          ]);
        }
      } else if (
        response.data.status === "continue" ||
        response.data.status === "success"
      ) {
        // Continue interview
        const assistantMessage =
          response.data.data?.reply ||
          response.data.data?.question ||
          response.data.message ||
          "Please continue...";

        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: assistantMessage },
        ]);
        if (response.data.data?.context) {
          setContext(response.data.data.context);
        }
      } else if (response.data.status === "error") {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `Error: ${response.data.message || "Failed to process request"}`,
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "Unexpected response. Please try again.",
          },
        ]);
      }
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Error sending message. Please try again.",
        },
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
          <p className="text-gray-600 dark:text-gray-400">
            Starting campaign setup...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
        <p className="text-sm text-blue-800 dark:text-blue-300">
          <strong>Creating:</strong> {moduleName} Campaign
        </p>
      </div>

      <div className="flex flex-col h-[400px]">
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50 dark:bg-gray-800 rounded-lg mb-4">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${
                message.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2 ${
                  message.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
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
                  <div
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: "0.1s" }}
                  ></div>
                  <div
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: "0.2s" }}
                  ></div>
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
            onKeyPress={(e) => e.key === "Enter" && handleSend()}
            placeholder="Type your answer..."
            className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={isLoading || !!campaignId}
          />
          <Button onClick={handleSend} disabled={isLoading || !!campaignId}>
            Send
          </Button>
          {onSkip && (
            <Button
              onClick={onSkip}
              variant="outline"
              disabled={isLoading || !!campaignId}
            >
              Skip
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
