// app/(auth)/register/page.tsx
import RegisterForm from "@/components/auth/RegisterForm";

export default function RegisterPage() {
  return (
    <div className="w-full max-w-md">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-foreground mb-2">Apex OS</h1>
        <p className="text-muted-foreground">Create your account</p>
      </div>
      <div className="rounded-xl border border-border bg-card/80 backdrop-blur-sm shadow-lg p-6">
        <RegisterForm />
      </div>
    </div>
  );
}
