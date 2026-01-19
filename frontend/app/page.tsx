"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const success = await login(email, password);
      if (success) {
        router.push("/dashboard");
      } else {
        setError("Invalid credentials. Please try again.");
      }
    } catch (err) {
      setError("Login failed. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 p-4">
      <div className="w-full max-w-md">
        <Card className="bg-slate-900/50 border-purple-500/30 shadow-neon-purple">
          <CardHeader className="text-center">
            <div className="text-4xl mb-2">⚡</div>
            <CardTitle className="text-2xl text-purple-400">
              Apex Sovereign OS
            </CardTitle>
            <CardDescription className="text-slate-400">
              Secure Access Required
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label
                  htmlFor="email"
                  className="block text-sm font-medium text-slate-300 mb-2"
                >
                  Email / User ID
                </label>
                <input
                  id="email"
                  type="text"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full px-4 py-2 bg-slate-800 border border-purple-500/30 rounded-md text-slate-100 focus:outline-none focus:ring-2 focus:ring-purple-500/50"
                  placeholder="Enter your email"
                />
              </div>
              <div>
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-slate-300 mb-2"
                >
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full px-4 py-2 bg-slate-800 border border-purple-500/30 rounded-md text-slate-100 focus:outline-none focus:ring-2 focus:ring-purple-500/50"
                  placeholder="Enter your password"
                />
              </div>
              {error && (
                <div className="text-red-400 text-sm text-center">{error}</div>
              )}
              <Button
                type="submit"
                disabled={isLoading}
                className="w-full"
              >
                {isLoading ? "Logging in..." : "Login"}
              </Button>
            </form>
            <p className="mt-4 text-xs text-center text-slate-500">
              Authentication verified against SQL database.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
