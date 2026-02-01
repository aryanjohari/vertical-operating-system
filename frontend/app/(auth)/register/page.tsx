"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Mail, Lock, User, Building2, UserPlus } from "lucide-react";
import { auth } from "@/lib/api";
import { useAppStore } from "@/store/useAppStore";
import { AuthCard } from "@/components/auth/AuthCard";
import { cn } from "@/lib/utils";

const registerSchema = z.object({
  fullName: z.string().min(1, "Full name is required"),
  email: z.string().min(1, "Email is required").email("Invalid email address"),
  password: z.string().min(6, "Password must be at least 6 characters"),
  agencyName: z.string().optional(),
});

type RegisterFormData = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const router = useRouter();
  const login = useAppStore((s) => s.login);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: { fullName: "", email: "", password: "", agencyName: "" },
  });

  const onSubmit = async (data: RegisterFormData) => {
    setIsLoading(true);
    try {
      const result = await auth.register(
        data.email,
        data.password,
        data.fullName,
        data.agencyName
      );
      if (!result.success) {
        toast.error("Registration failed. Email may already be in use.", {
          style: { background: "hsl(0 100% 60% / 0.2)", borderColor: "hsl(0 100% 60%)" },
        });
        return;
      }
      // Auto-login after successful registration
      const loginResult = await login(data.email, data.password);
      if (loginResult.success) {
        router.push("/onboarding");
      } else {
        toast.success("Account created. Please sign in.", {
          style: { background: "hsl(180 100% 50% / 0.1)", borderColor: "hsl(180 100% 50%)" },
        });
        router.push("/login");
      }
    } catch {
      toast.error("Registration failed. Please try again.", {
        style: { background: "hsl(0 100% 60% / 0.2)", borderColor: "hsl(0 100% 60%)" },
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthCard>
      <div className="space-y-6">
        <h1 className="acid-text text-2xl font-bold text-foreground">Create Account</h1>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label htmlFor="fullName" className="block text-sm font-medium text-foreground">
              Full Name
            </label>
            <div className="relative mt-1">
              <User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                id="fullName"
                type="text"
                placeholder="Jane Smith"
                autoComplete="name"
                disabled={isLoading}
                className={cn(
                  "w-full rounded border bg-muted/50 py-2 pl-10 pr-3 text-foreground placeholder:text-muted-foreground",
                  "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background",
                  "disabled:cursor-not-allowed disabled:opacity-60",
                  errors.fullName ? "border-primary" : "border-border"
                )}
                {...register("fullName")}
              />
            </div>
            {errors.fullName && (
              <p className="mt-1 text-sm text-primary">{errors.fullName.message}</p>
            )}
          </div>
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
                autoComplete="new-password"
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
          <div>
            <label htmlFor="agencyName" className="block text-sm font-medium text-foreground">
              Agency Name <span className="text-muted-foreground">(optional)</span>
            </label>
            <div className="relative mt-1">
              <Building2 className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                id="agencyName"
                type="text"
                placeholder="Acme Digital"
                autoComplete="organization"
                disabled={isLoading}
                className={cn(
                  "w-full rounded border bg-muted/50 py-2 pl-10 pr-3 text-foreground placeholder:text-muted-foreground",
                  "focus:outline-none focus:ring-2 focus:ring-secondary focus:ring-offset-2 focus:ring-offset-background",
                  "disabled:cursor-not-allowed disabled:opacity-60",
                  "border-border"
                )}
                {...register("agencyName")}
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={isLoading}
            className="acid-glow flex w-full items-center justify-center gap-2 rounded bg-primary px-4 py-2.5 font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <UserPlus className="h-4 w-4" />
            {isLoading ? "Creating account..." : "Register"}
          </button>
        </form>
        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link href="/login" className="text-secondary hover:underline">
            Sign In
          </Link>
        </p>
      </div>
    </AuthCard>
  );
}
