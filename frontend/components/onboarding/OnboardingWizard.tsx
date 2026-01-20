"use client";

import { useState, useEffect, useRef } from "react";
import { MapPin, Phone, Share2, Check, Loader2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  analyzeBusinessUrl,
  startOnboardingInterview,
  continueOnboardingInterview,
} from "@/lib/api";
import type { BusinessIdentity, AgentOutput } from "@/lib/types";

interface OnboardingWizardProps {
  user_id: string;
  onComplete?: (projectId: string) => void;
  onClose?: () => void;
}

type Phase = 1 | 2 | 3 | "complete";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export function OnboardingWizard({ user_id, onComplete, onClose }: OnboardingWizardProps) {
  const [phase, setPhase] = useState<Phase>(1);
  const [url, setUrl] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [identity, setIdentity] = useState<BusinessIdentity | null>(null);
  const [selectedModules, setSelectedModules] = useState<string[]>([]);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [currentMessage, setCurrentMessage] = useState("");
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [interviewContext, setInterviewContext] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const modules = [
    {
      key: "local_seo",
      name: "Apex Growth (pSEO)",
      description: "Dominate Google Maps.",
      icon: MapPin,
      enabled: true,
    },
    {
      key: "lead_gen",
      name: "Apex Connect (Lead Gen)",
      description: "24/7 Voice & Lead Capture.",
      icon: Phone,
      enabled: true,
    },
    {
      key: "social_media",
      name: "Social Suite",
      description: "Automated Posting.",
      icon: Share2,
      enabled: false,
    },
  ];

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (phase === 3 && chatHistory.length === 0) {
      // Start the interview when Phase 3 mounts
      startInterview();
    }
  }, [phase]);

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory]);

  const handleAnalyzeUrl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) {
      setError("Please enter a valid URL");
      return;
    }

    // Basic URL validation
    if (!url.startsWith("http://") && !url.startsWith("https://")) {
      setError("URL must start with http:// or https://");
      return;
    }

    setError(null);
    setIsAnalyzing(true);

    try {
      const response: AgentOutput = await analyzeBusinessUrl(user_id, url);
      
      if (response.status === "success" && response.data?.identity) {
        setIdentity(response.data.identity);
      } else {
        setError(response.message || "Failed to analyze URL");
      }
    } catch (err: any) {
      setError(err.message || "An error occurred while analyzing the URL");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleConfirmIdentity = () => {
    if (!identity?.business_name || !identity?.niche) {
      setError("Business name and niche are required");
      return;
    }
    setError(null);
    setPhase(2);
  };

  const toggleModule = (moduleKey: string, enabled: boolean) => {
    if (!enabled) return; // Can't toggle disabled modules
    
    setSelectedModules((prev) =>
      prev.includes(moduleKey)
        ? prev.filter((key) => key !== moduleKey)
        : [...prev, moduleKey]
    );
  };

  const handleBeginSetup = () => {
    if (selectedModules.length === 0) {
      setError("Please select at least one module");
      return;
    }
    setError(null);
    
    // Generate project_id from niche or business name before starting interview
    if (identity) {
      const projectId = identity.niche
        .toLowerCase()
        .replace(/[^a-z0-9]/g, "_")
        .replace(/_+/g, "_")
        .replace(/^_|_$/g, "") || 
        identity.business_name
          .toLowerCase()
          .replace(/[^a-z0-9]/g, "_")
          .replace(/_+/g, "_")
          .replace(/^_|_$/g, "");
      
      setIdentity({
        ...identity,
        project_id: projectId,
      });
    }
    
    setPhase(3);
  };

  const startInterview = async () => {
    if (!identity || selectedModules.length === 0) return;

    // Ensure project_id is set in identity
    let identityWithProjectId = { ...identity };
    if (!identityWithProjectId.project_id) {
      const projectId = identity.niche
        .toLowerCase()
        .replace(/[^a-z0-9]/g, "_")
        .replace(/_+/g, "_")
        .replace(/^_|_$/g, "") || 
        identity.business_name
          .toLowerCase()
          .replace(/[^a-z0-9]/g, "_")
          .replace(/_+/g, "_")
          .replace(/^_|_$/g, "");
      identityWithProjectId.project_id = projectId;
      setIdentity(identityWithProjectId);
    }

    setIsChatLoading(true);
    setError(null);

    try {
      const response: AgentOutput = await startOnboardingInterview(
        user_id,
        identityWithProjectId,
        selectedModules
      );

      if (response.status === "continue" || response.status === "success") {
        const firstMessage = response.data?.reply || response.message;
        setChatHistory([{ role: "assistant", content: firstMessage }]);
        setInterviewContext(response.data?.context || { identity, modules: selectedModules });
      } else {
        setError(response.message || "Failed to start interview");
      }
    } catch (err: any) {
      setError(err.message || "An error occurred while starting the interview");
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentMessage.trim() || isChatLoading) return;

    const userMessage = currentMessage.trim();
    setCurrentMessage("");
    
    // Add user message to history
    const newHistory = [...chatHistory, { role: "user" as const, content: userMessage }];
    setChatHistory(newHistory);
    setIsChatLoading(true);
    setError(null);

    try {
      const response: AgentOutput = await continueOnboardingInterview(
        user_id,
        newHistory,
        userMessage,
        interviewContext || { identity, modules: selectedModules }
      );

      if (response.status === "complete") {
        // Interview is complete, extract project_id
        const completedProjectId = 
          response.data?.path?.split("/").pop() ||
          (identity?.project_id) ||
          identity?.niche?.toLowerCase().replace(/[^a-z0-9]/g, "_") ||
          "new_project";
        
        setProjectId(completedProjectId);
        setPhase("complete");
        setChatHistory([
          ...newHistory,
          { role: "assistant", content: response.data?.reply || "Configuration saved. System ready." },
        ]);
      } else if (response.status === "continue" || response.status === "success") {
        // Add AI response to history
        const aiMessage = response.data?.reply || response.message;
        setChatHistory([...newHistory, { role: "assistant", content: aiMessage }]);
        
        // Update context if provided
        if (response.data?.context) {
          setInterviewContext(response.data.context);
        }
      } else {
        setError(response.message || "An error occurred");
      }
    } catch (err: any) {
      setError(err.message || "An error occurred while sending your message");
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleGoToDashboard = () => {
    if (onComplete && projectId) {
      onComplete(projectId);
    }
    if (onClose) {
      onClose();
    }
  };

  // Phase 1: The Cold Read (Identity)
  if (phase === 1) {
    return (
      <div className="space-y-4">
        <Card className="border-emerald-500/30 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="text-emerald-400">The Cold Read</CardTitle>
            <CardDescription>Enter your business website URL to begin auto-discovery</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAnalyzeUrl} className="space-y-4">
              <div>
                <label htmlFor="url" className="block text-sm font-medium text-slate-300 mb-2">
                  Business Website URL
                </label>
                <input
                  id="url"
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com"
                  className="w-full px-4 py-2 bg-slate-800 border border-purple-500/30 rounded-md text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                  disabled={isAnalyzing}
                />
              </div>
              {error && (
                <div className="text-red-400 text-sm">{error}</div>
              )}
              <Button
                type="submit"
                disabled={isAnalyzing || !url.trim()}
                className="w-full bg-emerald-600 hover:bg-emerald-700"
              >
                {isAnalyzing ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  "Analyze Business"
                )}
              </Button>
            </form>

            {identity && (
              <div className="mt-6 space-y-4">
                <div className="border-t border-purple-500/20 pt-4">
                  <h3 className="text-lg font-semibold text-purple-300 mb-4">Business Identity</h3>
                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm font-medium text-slate-400 mb-1">
                        Business Name *
                      </label>
                      <input
                        type="text"
                        value={identity.business_name || ""}
                        onChange={(e) =>
                          setIdentity({ ...identity, business_name: e.target.value })
                        }
                        className="w-full px-3 py-2 bg-slate-800 border border-purple-500/30 rounded-md text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-400 mb-1">
                        Niche *
                      </label>
                      <input
                        type="text"
                        value={identity.niche || ""}
                        onChange={(e) =>
                          setIdentity({ ...identity, niche: e.target.value })
                        }
                        className="w-full px-3 py-2 bg-slate-800 border border-purple-500/30 rounded-md text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-400 mb-1">
                        Phone
                      </label>
                      <input
                        type="tel"
                        value={identity.phone || ""}
                        onChange={(e) =>
                          setIdentity({ ...identity, phone: e.target.value })
                        }
                        className="w-full px-3 py-2 bg-slate-800 border border-purple-500/30 rounded-md text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-400 mb-1">
                        Email
                      </label>
                      <input
                        type="email"
                        value={identity.email || ""}
                        onChange={(e) =>
                          setIdentity({ ...identity, email: e.target.value })
                        }
                        className="w-full px-3 py-2 bg-slate-800 border border-purple-500/30 rounded-md text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-400 mb-1">
                        Address
                      </label>
                      <input
                        type="text"
                        value={identity.address || ""}
                        onChange={(e) =>
                          setIdentity({ ...identity, address: e.target.value })
                        }
                        className="w-full px-3 py-2 bg-slate-800 border border-purple-500/30 rounded-md text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                      />
                    </div>
                  </div>
                </div>
                <Button
                  onClick={handleConfirmIdentity}
                  className="w-full bg-emerald-600 hover:bg-emerald-700"
                >
                  Confirm & Continue
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  // Phase 2: The App Store (Modules)
  if (phase === 2) {
    return (
      <div className="space-y-4">
        <Card className="border-emerald-500/30 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="text-emerald-400">The App Store</CardTitle>
            <CardDescription>Select the modules you want to activate</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-4 mb-4">
              {modules.map((module) => {
                const Icon = module.icon;
                const isSelected = selectedModules.includes(module.key);
                return (
                  <Card
                    key={module.key}
                    className={`cursor-pointer transition-all ${
                      isSelected
                        ? "border-emerald-500 bg-emerald-500/10"
                        : "border-purple-500/30 hover:border-purple-500/50"
                    } ${!module.enabled ? "opacity-50 cursor-not-allowed" : ""}`}
                    onClick={() => toggleModule(module.key, module.enabled)}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-start gap-3">
                        <div
                          className={`flex-shrink-0 w-10 h-10 rounded-md flex items-center justify-center ${
                            isSelected
                              ? "bg-emerald-500/20 text-emerald-400"
                              : "bg-purple-500/10 text-purple-400"
                          }`}
                        >
                          <Icon className="w-5 h-5" />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center justify-between mb-1">
                            <h4 className="font-semibold text-slate-200">{module.name}</h4>
                            {isSelected && (
                              <Check className="w-5 h-5 text-emerald-400" />
                            )}
                          </div>
                          <p className="text-sm text-slate-400">{module.description}</p>
                          {!module.enabled && (
                            <p className="text-xs text-slate-500 mt-1">Coming Soon</p>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
            {error && <div className="text-red-400 text-sm mb-4">{error}</div>}
            <Button
              onClick={handleBeginSetup}
              disabled={selectedModules.length === 0}
              className="w-full bg-emerald-600 hover:bg-emerald-700"
            >
              Begin Setup
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Phase 3: The Genesis Chat (Interview)
  if (phase === 3) {
    return (
      <div className="space-y-4">
        <Card className="border-emerald-500/30 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="text-emerald-400">The Genesis Interview</CardTitle>
            <CardDescription>Answer a few questions to configure your system</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Chat Messages */}
              <div className="h-64 overflow-y-auto bg-slate-950/50 rounded-md p-4 space-y-4 border border-purple-500/20">
                {isChatLoading && chatHistory.length === 0 ? (
                  <div className="flex items-center justify-center h-full">
                    <Loader2 className="w-6 h-6 animate-spin text-emerald-400" />
                  </div>
                ) : (
                  <>
                    {chatHistory.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`flex ${
                          msg.role === "user" ? "justify-end" : "justify-start"
                        }`}
                      >
                        <div
                          className={`max-w-[80%] rounded-lg px-4 py-2 ${
                            msg.role === "user"
                              ? "bg-emerald-600 text-white"
                              : "bg-slate-800 text-slate-200 border border-purple-500/30"
                          }`}
                        >
                          <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                        </div>
                      </div>
                    ))}
                    {isChatLoading && (
                      <div className="flex justify-start">
                        <div className="bg-slate-800 rounded-lg px-4 py-2 border border-purple-500/30">
                          <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
                        </div>
                      </div>
                    )}
                    <div ref={chatEndRef} />
                  </>
                )}
              </div>

              {/* Chat Input */}
              {error && <div className="text-red-400 text-sm">{error}</div>}
              <form onSubmit={handleSendMessage} className="flex gap-2">
                <input
                  type="text"
                  value={currentMessage}
                  onChange={(e) => setCurrentMessage(e.target.value)}
                  placeholder="Type your answer..."
                  className="flex-1 px-4 py-2 bg-slate-800 border border-purple-500/30 rounded-md text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                  disabled={isChatLoading}
                />
                <Button
                  type="submit"
                  disabled={isChatLoading || !currentMessage.trim()}
                  className="bg-emerald-600 hover:bg-emerald-700"
                >
                  {isChatLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    "Send"
                  )}
                </Button>
              </form>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Completion Screen
  if (phase === "complete") {
    return (
      <div className="space-y-4">
        <Card className="border-emerald-500/30 bg-slate-900/50">
          <CardHeader className="text-center">
            <div className="text-6xl mb-4">✨</div>
            <CardTitle className="text-emerald-400 text-2xl">Dashboard Ready!</CardTitle>
            <CardDescription className="text-lg">
              Your project has been configured and is ready to use.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-center space-y-4">
              <p className="text-slate-300">
                Configuration saved successfully. You can now access your dashboard.
              </p>
              <Button
                onClick={handleGoToDashboard}
                className="bg-emerald-600 hover:bg-emerald-700"
                size="lg"
              >
                Go to Dashboard
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return null;
}
