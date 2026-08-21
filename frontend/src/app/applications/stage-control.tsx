'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';

import { cn } from '@/lib/utils';

import type { Stage, StageInfo } from './types';

/**
 * Move one application to another stage.
 *
 * A round trip rather than optimistic state: the move is written to the
 * timeline server-side, and the date it happened is the thing the tracker
 * exists to remember.
 */
export function StageControl({
  applicationId,
  stage,
  stages,
  size = 'sm',
}: {
  applicationId: number;
  stage: Stage;
  stages: StageInfo[];
  size?: 'sm' | 'md';
}) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function move(next: string) {
    if (next === stage) return;
    setPending(true);
    setError(null);
    try {
      const response = await fetch(`/api/applications/${applicationId}/stage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage: next }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setError(typeof data.detail === 'string' ? data.detail : 'Could not move it.');
        return;
      }
      router.refresh();
    } catch {
      setError('Could not reach the server.');
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="inline-flex items-center gap-1.5">
      <label className="sr-only" htmlFor={`stage-${applicationId}`}>
        Stage
      </label>
      <select
        id={`stage-${applicationId}`}
        value={stage}
        disabled={pending}
        onChange={(event) => move(event.target.value)}
        className={cn(
          'rounded-lg border border-input bg-transparent px-2 outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30',
          size === 'sm' ? 'h-7 text-xs' : 'h-8 text-sm',
        )}
      >
        {stages.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {pending && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
      {error && (
        <span role="alert" className="text-xs text-destructive">
          {error}
        </span>
      )}
    </div>
  );
}
