'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Check, Loader2, Plus } from 'lucide-react';

import { Button } from '@/components/ui/button';

/** Appends a missing skill (and its prerequisites) to the active roadmap. */
export function AddToRoadmapButton({ conceptSlugs }: { conceptSlugs: string[] }) {
  const router = useRouter();
  const [state, setState] = useState<'idle' | 'pending' | 'done' | 'error'>('idle');

  async function add() {
    setState('pending');
    const response = await fetch('/api/roadmaps/current/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ concept_slugs: conceptSlugs }),
    });
    if (!response.ok) {
      setState('error');
      return;
    }
    setState('done');
    router.refresh();
  }

  if (state === 'done') {
    return (
      <p className="mt-4 flex items-center justify-center gap-2 text-sm text-success">
        <Check className="h-4 w-4" />
        Added to your roadmap
      </p>
    );
  }

  return (
    <>
      <Button
        variant="secondary"
        className="mt-4 w-full"
        onClick={add}
        disabled={state === 'pending' || conceptSlugs.length === 0}
      >
        {state === 'pending' ? <Loader2 className="animate-spin" /> : <Plus />}
        Add these to my roadmap
      </Button>
      {state === 'error' && (
        <p role="alert" className="mt-2 text-center text-sm text-destructive">
          Could not add them. Do you have a roadmap yet?
        </p>
      )}
    </>
  );
}
