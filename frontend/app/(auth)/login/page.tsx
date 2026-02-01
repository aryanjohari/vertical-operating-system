// app/(auth)/login/page.tsx
import LoginForm from "@/components/auth/LoginForm";

export default function LoginPage() {
  return (
    <div className="w-full max-w-md">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-foreground mb-2">Apex OS</h1>
        <p className="text-muted-foreground">Sign in to your account</p>
      </div>
      <div className="rounded-xl border border-border bg-card/80 backdrop-blur-sm shadow-lg p-6">
        <LoginForm />
      </div>
    </div>
  );
}
