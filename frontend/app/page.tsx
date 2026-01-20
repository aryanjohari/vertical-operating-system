"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { registerUser } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState("");
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

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password !== registerConfirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    if (!email.trim()) {
      setError("Email is required");
      return;
    }

    setIsLoading(true);

    try {
      const result = await registerUser(email, password);
      if (result.success) {
        // Auto-login after successful registration
        const loginSuccess = await login(email, password);
        if (loginSuccess) {
          router.push("/dashboard");
        } else {
          setError("Account created but login failed. Please try logging in.");
        }
      } else {
        setError("Registration failed. User may already exist.");
      }
    } catch (err) {
      setError("Registration failed. Please try again.");
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
            {/* Tab Switcher */}
            <div className="flex gap-2 mb-6">
              <button
                type="button"
                onClick={() => {
                  setIsRegisterMode(false);
                  setError("");
                  setRegisterConfirmPassword("");
                }}
                className={`flex-1 py-2 px-4 rounded-md transition-colors text-sm font-medium ${
                  !isRegisterMode
                    ? "bg-purple-600 text-white"
                    : "bg-slate-800 text-slate-400 hover:text-slate-200"
                }`}
              >
                Login
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsRegisterMode(true);
                  setError("");
                  setRegisterConfirmPassword("");
                }}
                className={`flex-1 py-2 px-4 rounded-md transition-colors text-sm font-medium ${
                  isRegisterMode
                    ? "bg-purple-600 text-white"
                    : "bg-slate-800 text-slate-400 hover:text-slate-200"
                }`}
              >
                Register
              </button>
            </div>

            {!isRegisterMode ? (
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
            ) : (
              <form onSubmit={handleRegister} className="space-y-4">
                <div>
                  <label
                    htmlFor="register-email"
                    className="block text-sm font-medium text-slate-300 mb-2"
                  >
                    Email / User ID
                  </label>
                  <input
                    id="register-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full px-4 py-2 bg-slate-800 border border-purple-500/30 rounded-md text-slate-100 focus:outline-none focus:ring-2 focus:ring-purple-500/50"
                    placeholder="Enter your email"
                  />
                </div>
                <div>
                  <label
                    htmlFor="register-password"
                    className="block text-sm font-medium text-slate-300 mb-2"
                  >
                    Password
                  </label>
                  <input
                    id="register-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={6}
                    className="w-full px-4 py-2 bg-slate-800 border border-purple-500/30 rounded-md text-slate-100 focus:outline-none focus:ring-2 focus:ring-purple-500/50"
                    placeholder="Enter your password (min 6 characters)"
                  />
                </div>
                <div>
                  <label
                    htmlFor="register-confirm"
                    className="block text-sm font-medium text-slate-300 mb-2"
                  >
                    Confirm Password
                  </label>
                  <input
                    id="register-confirm"
                    type="password"
                    value={registerConfirmPassword}
                    onChange={(e) => setRegisterConfirmPassword(e.target.value)}
                    required
                    className="w-full px-4 py-2 bg-slate-800 border border-purple-500/30 rounded-md text-slate-100 focus:outline-none focus:ring-2 focus:ring-purple-500/50"
                    placeholder="Confirm your password"
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
                  {isLoading ? "Creating account..." : "Create Account"}
                </Button>
              </form>
            )}
            <p className="mt-4 text-xs text-center text-slate-500">
              {isRegisterMode
                ? "Create a new account to get started."
                : "Authentication verified against SQL database."}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
