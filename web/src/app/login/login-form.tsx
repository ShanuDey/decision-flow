"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authClient } from "@/lib/auth/client";
import { type Method, PASSWORD } from "@/lib/auth/config";
import { methodLabel } from "@/lib/auth/format";

export function LoginForm({ methods, next }: { methods: Method[]; next: string }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const social = methods.filter((m) => m !== PASSWORD);
  const password = methods.includes(PASSWORD);

  // Back from a provider restores this page from the browser cache with the buttons still disabled.
  useEffect(() => {
    const reset = (event: PageTransitionEvent) => {
      if (event.persisted) setBusy(false);
    };
    window.addEventListener("pageshow", reset);
    return () => window.removeEventListener("pageshow", reset);
  }, []);

  async function signInWithPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    const { error: failure } = await authClient.signIn.email({
      email: String(form.get("email")),
      password: String(form.get("password")),
    });
    if (failure) {
      setError(failure.status === 429 ? "Too many attempts. Try again shortly." : "Invalid email or password.");
      setBusy(false);
      return;
    }
    router.push(next);
    router.refresh();
  }

  async function signInWithProvider(provider: Method) {
    setBusy(true);
    setError(null);
    const { error: failure } = await authClient.signIn.social({ provider, callbackURL: next });
    if (failure) {
      setError(`Could not start ${methodLabel(provider)} sign-in.`);
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {password && (
        <form onSubmit={signInWithPassword} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" name="email" type="email" autoComplete="username" required />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
          </div>
          <Button type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      )}

      {password && social.length > 0 && (
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="h-px flex-1 bg-border" />
          or
          <span className="h-px flex-1 bg-border" />
        </div>
      )}

      {social.map((provider) => (
        <Button
          key={provider}
          type="button"
          variant="outline"
          disabled={busy}
          onClick={() => signInWithProvider(provider)}
        >
          Continue with {methodLabel(provider)}
        </Button>
      ))}

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
