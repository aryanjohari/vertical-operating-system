export default function OnboardingPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-8 p-8">
      <h1 className="acid-text text-3xl font-bold text-foreground">
        Project Onboarding
      </h1>
      {/* Step indicators */}
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div className="flex flex-col items-center">
          <span className="flex h-8 w-8 items-center justify-center rounded bg-primary text-sm font-medium text-primary-foreground">
            1
          </span>
          <span className="mt-1 text-xs text-muted-foreground">Identity</span>
        </div>
        <div className="h-px flex-1 bg-border" />
        <div className="flex flex-col items-center">
          <span className="flex h-8 w-8 items-center justify-center rounded border border-border bg-muted text-sm font-medium text-muted-foreground">
            2
          </span>
          <span className="mt-1 text-xs text-muted-foreground">Contact</span>
        </div>
        <div className="h-px flex-1 bg-border" />
        <div className="flex flex-col items-center">
          <span className="flex h-8 w-8 items-center justify-center rounded border border-border bg-muted text-sm font-medium text-muted-foreground">
            3
          </span>
          <span className="mt-1 text-xs text-muted-foreground">Voice</span>
        </div>
      </div>
      {/* Placeholder content for step 1 */}
      <div className="glass-panel p-6">
        <h2 className="mb-4 text-lg font-semibold text-foreground">
          Identity
        </h2>
        <p className="text-sm text-muted-foreground">
          Project identity form will go here.
        </p>
      </div>
    </div>
  );
}
