import { cn } from "@/lib/utils";

interface PulseCardProps {
  title: string;
  primary: React.ReactNode;
  secondary?: React.ReactNode;
  className?: string;
}

export function PulseCard({ title, primary, secondary, className }: PulseCardProps) {
  return (
    <div
      className={cn(
        "glass-panel flex flex-col gap-2 p-6",
        "border-l-2 border-l-primary/50",
        className
      )}
    >
      <p className="text-sm text-muted-foreground">{title}</p>
      <p className="text-3xl font-bold text-foreground">{primary}</p>
      {secondary != null && (
        <p className="text-sm text-muted-foreground">{secondary}</p>
      )}
    </div>
  );
}

export function PulseCardSkeleton() {
  return (
    <div className="glass-panel animate-pulse p-6">
      <div className="h-4 w-24 rounded bg-muted" />
      <div className="mt-2 h-8 w-16 rounded bg-muted" />
      <div className="mt-2 h-3 w-32 rounded bg-muted" />
    </div>
  );
}
