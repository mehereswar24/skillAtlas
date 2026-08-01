'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowUp, Loader2, MessageSquare, PenLine, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import type { CommunityPost, Domain } from '@/lib/types';

export function CommunityFeed({
  initialPosts,
  domains,
  signedIn,
  sort,
  domainFilter,
}: {
  initialPosts: CommunityPost[];
  domains: Domain[];
  signedIn: boolean;
  sort: 'new' | 'top';
  domainFilter?: string;
}) {
  const router = useRouter();
  const [posts, setPosts] = useState(initialPosts);
  const [composing, setComposing] = useState(false);

  async function vote(postId: number) {
    if (!signedIn) {
      router.push(`/login?next=${encodeURIComponent('/community')}`);
      return;
    }
    // Optimistic: the counter moves immediately and is corrected by the
    // server's authoritative response.
    setPosts((prev) =>
      prev.map((p) =>
        p.id === postId
          ? {
              ...p,
              viewer_has_voted: !p.viewer_has_voted,
              upvotes: p.upvotes + (p.viewer_has_voted ? -1 : 1),
            }
          : p,
      ),
    );

    const response = await fetch(`/api/community/posts/${postId}/vote`, { method: 'POST' });
    if (!response.ok) {
      router.refresh();
      return;
    }
    const data = await response.json();
    setPosts((prev) =>
      prev.map((p) =>
        p.id === postId
          ? { ...p, upvotes: data.upvotes, viewer_has_voted: data.viewer_has_voted }
          : p,
      ),
    );
  }

  return (
    <>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2">
          <SortLink active={sort === 'new'} href={buildHref('new', domainFilter)}>
            Newest
          </SortLink>
          <SortLink active={sort === 'top'} href={buildHref('top', domainFilter)}>
            Top
          </SortLink>
        </div>

        {signedIn ? (
          <Button onClick={() => setComposing((v) => !v)}>
            {composing ? <X /> : <PenLine />}
            {composing ? 'Cancel' : 'New post'}
          </Button>
        ) : (
          <Link
            href={`/login?next=${encodeURIComponent('/community')}`}
            className="text-sm font-medium text-primary hover:underline"
          >
            Sign in to post
          </Link>
        )}
      </div>

      {composing && (
        <PostComposer
          domains={domains}
          onCreated={(post) => {
            setPosts((prev) => [post, ...prev]);
            setComposing(false);
          }}
        />
      )}

      {posts.length === 0 ? (
        <p className="py-16 text-center text-muted-foreground">
          No posts yet. {signedIn ? 'Start the first discussion.' : 'Sign in to start one.'}
        </p>
      ) : (
        <ul className="space-y-3">
          {posts.map((post) => (
            <li key={post.id} className="flex gap-4 rounded-xl border bg-card p-5">
              <button
                type="button"
                onClick={() => vote(post.id)}
                aria-pressed={post.viewer_has_voted}
                aria-label={`Upvote ${post.title}`}
                className={cn(
                  'flex h-fit flex-col items-center gap-0.5 rounded-lg px-2 py-1.5 transition-colors',
                  post.viewer_has_voted
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                <ArrowUp className="h-4 w-4" />
                <span className="text-sm font-medium tabular-nums">{post.upvotes}</span>
              </button>

              <div className="min-w-0 flex-1">
                <div className="mb-1.5 flex flex-wrap items-center gap-2 text-xs">
                  {post.domain && (
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 font-medium text-primary">
                      {post.domain.name}
                    </span>
                  )}
                  <span className="text-muted-foreground">
                    by {post.author.display_name ?? 'someone'} ·{' '}
                    {formatRelative(post.created_at)}
                  </span>
                </div>

                <Link href={`/community/${post.id}`} className="group">
                  <h2 className="font-semibold group-hover:text-primary">{post.title}</h2>
                </Link>
                <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                  {post.content}
                </p>

                <Link
                  href={`/community/${post.id}`}
                  className="mt-3 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
                >
                  <MessageSquare className="h-4 w-4" />
                  {post.comment_count} {post.comment_count === 1 ? 'comment' : 'comments'}
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function PostComposer({
  domains,
  onCreated,
}: {
  domains: Domain[];
  onCreated: (post: CommunityPost) => void;
}) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [domainSlug, setDomainSlug] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const response = await fetch('/api/community/posts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          content,
          domain_slug: domainSlug || null,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(data.detail ?? 'Could not publish your post.');
        return;
      }
      onCreated(data);
    } catch {
      setError('Could not reach the server.');
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="mb-6 space-y-4 rounded-xl border bg-card p-5">
      <div className="space-y-2">
        <Label htmlFor="post-title">Title</Label>
        <Input
          id="post-title"
          required
          minLength={4}
          maxLength={255}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="What do you want to discuss?"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="post-content">Post</Label>
        <Textarea
          id="post-content"
          required
          rows={5}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Share what you tried, what worked, or what you are stuck on."
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="post-domain">Domain (optional)</Label>
        <select
          id="post-domain"
          value={domainSlug}
          onChange={(e) => setDomainSlug(e.target.value)}
          className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">No domain</option>
          {domains.map((domain) => (
            <option key={domain.slug} value={domain.slug}>
              {domain.name}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      <Button type="submit" disabled={pending || title.length < 4 || !content.trim()}>
        {pending && <Loader2 className="animate-spin" />}
        Publish
      </Button>
    </form>
  );
}

function SortLink({
  active,
  href,
  children,
}: {
  active: boolean;
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors',
        active
          ? 'border-primary bg-primary text-primary-foreground'
          : 'hover:border-primary/50 hover:bg-muted',
      )}
    >
      {children}
    </Link>
  );
}

function buildHref(sort: string, domain?: string): string {
  const params = new URLSearchParams({ sort });
  if (domain) params.set('domain', domain);
  return `/community?${params}`;
}

export function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 60) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
