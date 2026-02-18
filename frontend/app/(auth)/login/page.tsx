"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Mail, Lock, LogIn } from "lucide-react";
import { useAppStore } from "@/store/useAppStore";
import { AuthCard } from "@/components/auth/AuthCard";
import { cn } from "@/lib/utils";

const loginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Invalid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormData = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const login = useAppStore((s) => s.login);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = async (data: LoginFormData) => {
    setIsLoading(true);
    try {
      const result = await login(data.email, data.password);
      if (result.success) {
        router.push("/projects");
      } else {
        toast.error(result.error ?? "Invalid credentials", {
          style: { background: "hsl(0 100% 60% / 0.2)", borderColor: "hsl(0 100% 60%)" },
        });
      }
    } catch {
      toast.error("Login failed. Please try again.", {
        style: { background: "hsl(0 100% 60% / 0.2)", borderColor: "hsl(0 100% 60%)" },
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthCard>
      <div className="space-y-6">
        <h1 className="acid-text text-2xl font-bold text-foreground">Sign In</h1>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-foreground">
              Email
            </label>
            <div className="relative mt-1">
              <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                id="email"
                type="email"
                placeholder="you@example.com"
                autoComplete="email"
                disabled={isLoading}
                className={cn(
                  "w-full rounded border bg-muted/50 py-2 pl-10 pr-3 text-foreground placeholder:text-muted-foreground",
                  "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background",
                  "disabled:cursor-not-allowed disabled:opacity-60",
                  errors.email ? "border-primary" : "border-border"
                )}
                {...register("email")}
              />
            </div>
            {errors.email && (
              <p className="mt-1 text-sm text-primary">{errors.email.message}</p>
            )}
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-foreground">
              Password
            </label>
            <div className="relative mt-1">
              <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                id="password"
                type="password"
                placeholder="••••••••"
                autoComplete="current-password"
                disabled={isLoading}
                className={cn(
                  "w-full rounded border bg-muted/50 py-2 pl-10 pr-3 text-foreground placeholder:text-muted-foreground",
                  "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background",
                  "disabled:cursor-not-allowed disabled:opacity-60",
                  errors.password ? "border-primary" : "border-border"
                )}
                {...register("password")}
              />
            </div>
            {errors.password && (
              <p className="mt-1 text-sm text-primary">{errors.password.message}</p>
            )}
          </div>
          <button
            type="submit"
            disabled={isLoading}
            className="acid-glow flex w-full items-center justify-center gap-2 rounded bg-primary px-4 py-2.5 font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <LogIn className="h-4 w-4" />
            {isLoading ? "Signing in..." : "Sign In"}
          </button>
        </form>
        <p className="text-center text-sm text-muted-foreground">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="text-secondary hover:underline">
            Register
          </Link>
        </p>
      </div>
    </AuthCard>
  );
}
