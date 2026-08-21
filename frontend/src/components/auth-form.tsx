'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { BrainCircuit, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

type Mode = 'login' | 'signup';

const COPY = {
  login: {
    title: 'Welcome back',
    subtitle: 'Sign in to pick up where you left off',
    submit: 'Sign in',
    switchPrompt: "Don't have an account?",
    switchLabel: 'Create one',
    switchHref: '/signup',
  },
  signup: {
    title: 'Create your account',
    subtitle: 'Build a roadmap that adapts to how much time you actually have',
    submit: 'Create account',
    switchPrompt: 'Already have an account?',
    switchLabel: 'Sign in',
    switchHref: '/login',
  },
} as const;

export function AuthForm({ mode, next }: { mode: Mode; next?: string }) {
  const router = useRouter();
  const copy = COPY[mode];

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (mode === 'signup' && password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }

    setPending(true);
    try {
      const response = await fetch(`/api/auth/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          mode === 'signup'
            ? { email, password, display_name: displayName || null }
            : { email, password },
        ),
      });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(data.detail ?? 'Something went wrong. Please try again.');
        return;
      }

      // A brand-new account has no roadmap yet, so send them to set one up.
      const destination =
        next ?? (mode === 'signup' ? '/explore' : '/dashboard');
      router.push(destination);
      router.refresh();
    } catch {
      setError('Could not reach the server. Is the backend running?');
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="w-full max-w-md">
      <div className="mb-8 flex flex-col items-center text-center">
        <Link href="/" className="mb-6 inline-flex items-center gap-2">
          <BrainCircuit className="h-9 w-9 text-primary" />
          <span className="font-display text-2xl font-semibold">Skill<span className="text-primary">Atlas</span></span>
        </Link>
        <h1 className="font-display text-3xl font-semibold">{copy.title}</h1>
        <p className="mt-2 text-muted-foreground">{copy.subtitle}</p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-4 rounded-lg border bg-card p-8"
        noValidate
      >
        {mode === 'signup' && (
          <div className="space-y-2">
            <Label htmlFor="display_name">Name</Label>
            <Input
              id="display_name"
              name="display_name"
              autoComplete="name"
              placeholder="How should we address you?"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              disabled={pending}
            />
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            name="email"
            type="email"
            required
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={pending}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            name="password"
            type="password"
            required
            minLength={mode === 'signup' ? 8 : undefined}
            autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
            placeholder={mode === 'signup' ? 'At least 8 characters' : '••••••••'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={pending}
          />
        </div>

        {error && (
          <p
            role="alert"
            className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            {error}
          </p>
        )}

        <Button type="submit" size="lg" className="w-full" disabled={pending}>
          {pending && <Loader2 className="animate-spin" />}
          {pending ? 'Just a moment…' : copy.submit}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        {copy.switchPrompt}{' '}
        <Link
          href={next ? `${copy.switchHref}?next=${encodeURIComponent(next)}` : copy.switchHref}
          className="font-medium text-primary hover:underline"
        >
          {copy.switchLabel}
        </Link>
      </p>
    </div>
  );
}
