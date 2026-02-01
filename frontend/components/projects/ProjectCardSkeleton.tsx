export function ProjectCardSkeleton() {
  return (
    <div className="glass-panel animate-pulse p-6">
      <div className="flex items-start justify-between gap-2">
        <div className="h-5 w-32 rounded bg-muted" />
        <div className="h-5 w-14 rounded bg-muted" />
      </div>
      <div className="mt-3 h-4 w-24 rounded bg-muted" />
      <div className="mt-4 h-4 w-20 rounded bg-muted" />
    </div>
  );
}
