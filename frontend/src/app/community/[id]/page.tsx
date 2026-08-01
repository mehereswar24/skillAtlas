import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { ArrowLeft, ArrowUp, MessageSquare } from 'lucide-react';

import { AppShell } from '@/components/app-shell';
import { CommentForm } from '@/components/comment-form';
import { formatRelative } from '@/components/community-feed';
import { SiteHeader } from '@/components/site-header';
import { apiOrNull } from '@/lib/api';
import { getCurrentUser } from '@/lib/dal';
import type { CommunityComment, CommunityPost } from '@/lib/types';

type PostDetail = CommunityPost & { comments: CommunityComment[] };

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const post = await apiOrNull<PostDetail>(`/api/v1/community/posts/${id}`);
  return post ? { title: post.title } : { title: 'Post not found' };
}

export default async function PostPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [post, user] = await Promise.all([
    apiOrNull<PostDetail>(`/api/v1/community/posts/${id}`),
    getCurrentUser(),
  ]);
  if (!post) notFound();

  return (
    <AppShell>
      <SiteHeader />

      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-10 sm:px-6">
        <Link
          href="/community"
          className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          All discussions
        </Link>

        <article className="rounded-xl border bg-card p-6">
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
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

          <h1 className="font-display text-3xl font-semibold">{post.title}</h1>
          <p className="mt-4 whitespace-pre-wrap text-[15px] text-foreground/90">
            {post.content}
          </p>

          <div className="mt-6 flex items-center gap-4 border-t pt-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <ArrowUp className="h-4 w-4" />
              {post.upvotes} {post.upvotes === 1 ? 'upvote' : 'upvotes'}
            </span>
            <span className="flex items-center gap-1.5">
              <MessageSquare className="h-4 w-4" />
              {post.comment_count} {post.comment_count === 1 ? 'comment' : 'comments'}
            </span>
          </div>
        </article>

        <section className="mt-8">
          <h2 className="mb-4 font-display text-xl font-semibold">
            {post.comments.length} {post.comments.length === 1 ? 'comment' : 'comments'}
          </h2>

          {user ? (
            <CommentForm postId={post.id} />
          ) : (
            <p className="mb-6 rounded-xl border border-dashed bg-card p-4 text-sm text-muted-foreground">
              <Link
                href={`/login?next=${encodeURIComponent(`/community/${post.id}`)}`}
                className="font-medium text-primary hover:underline"
              >
                Sign in
              </Link>{' '}
              to join the discussion.
            </p>
          )}

          <ul className="space-y-3">
            {post.comments.map((comment) => (
              <li key={comment.id} className="rounded-xl border bg-card p-4">
                <p className="mb-1.5 text-xs text-muted-foreground">
                  {comment.author.display_name ?? 'someone'} ·{' '}
                  {formatRelative(comment.created_at)}
                </p>
                <p className="whitespace-pre-wrap text-sm">{comment.content}</p>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </AppShell>
  );
}
