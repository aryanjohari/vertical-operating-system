import { cn } from "@/lib/utils";

interface AuthCardProps {
  children: React.ReactNode;
  className?: string;
}

/**
 * Reusable Acid Noir auth card: glass panel with neon border accent.
 */
export function AuthCard({ children, className }: AuthCardProps) {
  return (
    <div
      className={cn(
        "w-full max-w-md rounded border border-border glass-panel p-8",
        "shadow-[0_0_20px_2px_hsl(0_100%_60%/0.08)]",
        className
      )}
    >
      {children}
    </div>
  );
}
