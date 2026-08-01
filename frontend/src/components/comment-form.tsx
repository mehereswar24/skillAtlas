'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, Send } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

export function CommentForm({ postId }: { postId: number }) {
  const router = useRouter();
  const [content, setContent] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const response = await fetch(`/api/community/posts/${postId}/comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setError(data.detail ?? 'Could not post your comment.');
        return;
      }
      setContent('');
      // Re-render the server component so the new comment appears in order.
      router.refresh();
    } catch {
      setError('Could not reach the server.');
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="mb-6 space-y-3 rounded-xl border bg-card p-4">
      <Textarea
        rows={3}
        required
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Add to the discussion…"
        aria-label="Your comment"
      />
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <Button type="submit" size="sm" disabled={pending || !content.trim()}>
        {pending ? <Loader2 className="animate-spin" /> : <Send />}
        Comment
      </Button>
    </form>
  );
}
