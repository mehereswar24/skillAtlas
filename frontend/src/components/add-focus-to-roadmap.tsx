'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Check, Loader2, Plus } from 'lucide-react';

import { Button } from '@/components/ui/button';

/**
 * Adds a company role's unmet focus areas to the learner's route.
 *
 * Deliberately a single button rather than a multi-select: the useful action
 * is "close the gap for this job", and the server already knows which concepts
 * that means and which prerequisites they drag along.
 */
export function AddFocusToRoadmap({
  companySlug,
  roleSlug,
  remaining,
}: {
  companySlug: string;
  roleSlug: string;
  remaining: number;
}) {
  const router = useRouter();
  const [state, setState] = useState<'idle' | 'pending' | 'done'>('idle');
  const [error, setError] = useState<string | null>(null);

  async function add() {
    setState('pending');
    setError(null);
    try {
      const response = await fetch(
        `/api/companies/${companySlug}/roles/${roleSlug}/add-to-roadmap`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ concept_slugs: [] }),
        },
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(data.detail ?? 'Could not update your route.');
        setState('idle');
        return;
      }
      setState('done');
      router.refresh();
    } catch {
      setError('Could not reach the server.');
      setState('idle');
    }
  }

  if (remaining === 0) {
    return (
      <p className="flex items-center gap-2 text-sm text-success">
        <Check className="h-4 w-4" />
        You have covered every focus area we can map for this role.
      </p>
    );
  }

  return (
    <div>
      <Button onClick={add} disabled={state !== 'idle'} size="sm">
        {state === 'pending' ? <Loader2 className="animate-spin" /> : state === 'done' ? <Check /> : <Plus />}
        {state === 'done'
          ? 'Added to your route'
          : `Add ${remaining} missing ${remaining === 1 ? 'area' : 'areas'} to my route`}
      </Button>
      {error && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
