'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import {
  CheckCircle,
  Loader2,
  MessageSquare,
  PlugZap,
  Send,
  Sparkles,
  Trash2,
  WifiOff,
  X,
} from 'lucide-react';

import { Markdown } from '@/components/markdown';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { ChatMessage, ChatSource } from '@/lib/types';

/** The places the helper knows how to be. Mirrors `PAGE_KINDS` on the API. */
export type TutorPage =
  | 'landing'
  | 'dashboard'
  | 'roadmap'
  | 'concept'
  | 'explore'
  | 'projects'
  | 'project'
  | 'companies'
  | 'company'
  | 'role'
  | 'community'
  | 'portfolio'
  | 'resume'
  | 'applications'
  | 'interviews'
  | 'other';

/**
 * Where the learner is, as the page reports it.
 *
 * Slugs and a page kind — never prose. The API resolves these against its own
 * tables and builds the description itself, so the model is told "this is the
 * role page for SDE-1 at Google, whose loop is …" rather than being handed a
 * URL and left to infer.
 */
export type TutorContext = {
  page?: TutorPage;
  conceptSlug?: string;
  companySlug?: string;
  roleSlug?: string;
  projectSlug?: string;
  trackSlug?: string;
};

type Opening = { greeting: string; suggestions: string[]; authenticated: boolean };

const FALLBACK_SUGGESTIONS = ['What is SkillAtlas?', 'What should I learn next?'];

/** How many prior turns an anonymous visitor replays; the API caps this too. */
const ANON_HISTORY_TURNS = 6;

/**
 * Derive the context from the path when a page has not passed one.
 *
 * A safety net, not the mechanism: pages that have real context pass it
 * explicitly and that always wins. Even here nothing but slugs crosses the
 * wire, and a slug that does not resolve on the server contributes nothing.
 */
function contextFromPath(pathname: string): TutorContext {
  const [, head, first, second] = pathname.split('/');

  if (!head) return { page: 'landing' };

  switch (head) {
    case 'concepts':
      return first ? { page: 'concept', conceptSlug: first } : { page: 'explore' };
    case 'projects':
      return first ? { page: 'project', projectSlug: first } : { page: 'projects' };
    case 'companies':
      if (first && second) {
        return { page: 'role', companySlug: first, roleSlug: second };
      }
      return first ? { page: 'company', companySlug: first } : { page: 'companies' };
    case 'dashboard':
    case 'roadmap':
    case 'explore':
    case 'community':
    case 'portfolio':
    case 'resume':
    case 'applications':
    case 'interviews':
      return { page: head };
    default:
      return { page: 'other' };
  }
}

function toPayload(context: TutorContext) {
  return {
    page: context.page ?? 'other',
    concept_slug: context.conceptSlug ?? null,
    company_slug: context.companySlug ?? null,
    role_slug: context.roleSlug ?? null,
    project_slug: context.projectSlug ?? null,
    track_slug: context.trackSlug ?? null,
  };
}

/**
 * The floating AI helper, present on every page including the public landing
 * page.
 *
 * Signed in, it talks to `/api/chat`: the learner's own history, their plan and
 * progress, and the tools that can edit their roadmap. Signed out it talks to
 * `/api/chat/public`, which has none of that — the conversation lives in this
 * component's state and nowhere else, and the API rate-limits it.
 *
 * Either way it consumes an SSE stream so tokens appear as they are generated,
 * and when Ollama is not running the stream still arrives, flagged degraded,
 * and the panel says so rather than showing a dead input.
 */
export function TutorLauncher({
  context,
  signedIn = false,
  conceptSlug,
}: {
  context?: TutorContext;
  signedIn?: boolean;
  /** @deprecated pass `context={{ page: 'concept', conceptSlug }}` instead. */
  conceptSlug?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();

  const resolved = useMemo<TutorContext>(() => {
    if (context) return context;
    if (conceptSlug) return { page: 'concept', conceptSlug };
    return contextFromPath(pathname ?? '/');
  }, [context, conceptSlug, pathname]);

  // A stable key so effects re-run on navigation but not on every render.
  const contextKey = JSON.stringify(toPayload(resolved));

  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [degraded, setDegraded] = useState(false);
  const [unreachable, setUnreachable] = useState(false);
  const [authed, setAuthed] = useState(signedIn);
  const [opening, setOpening] = useState<Opening | null>(null);
  const [roadmapAction, setRoadmapAction] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const loadedHistoryFor = useRef<string | null>(null);

  // Status and the opening offer. Re-run on navigation so the offer follows
  // the learner from a concept to a company page.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    (async () => {
      try {
        const [statusRes, openingRes] = await Promise.all([
          fetch('/api/chat/status'),
          fetch('/api/chat/opening', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ context: toPayload(resolved) }),
          }),
        ]);
        if (cancelled) return;

        if (!statusRes.ok) {
          setUnreachable(true);
          return;
        }
        const status = await statusRes.json();
        setUnreachable(false);
        setDegraded(!status.available);
        setAuthed(Boolean(status.authenticated));

        if (openingRes.ok) setOpening(await openingRes.json());
      } catch {
        if (!cancelled) setUnreachable(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [open, contextKey, resolved]);

  // Server-side history exists only for a signed-in learner.
  useEffect(() => {
    if (!open || !authed) return;
    if (loadedHistoryFor.current === 'done') return;
    loadedHistoryFor.current = 'done';

    (async () => {
      try {
        const response = await fetch('/api/chat/history?limit=20');
        if (!response.ok) return;
        const rows = await response.json();
        setMessages(
          rows.map((row: { role: string; content: string }) => ({
            role: row.role as ChatMessage['role'],
            content: row.content,
          })),
        );
      } catch {
        // History is a nicety; failing to load it must not block asking.
      }
    })();
  }, [open, authed]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, open]);

  const replaceLast = useCallback((content: string, sources?: ChatSource[]) => {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last?.role === 'assistant') {
        next[next.length - 1] = { ...last, content, sources };
      }
      return next;
    });
  }, []);

  async function send(text: string) {
    const question = text.trim();
    if (!question || streaming || unreachable) return;

    // Snapshot before the optimistic append, so the replay is the conversation
    // as it stood when the question was asked.
    const priorTurns = messages
      .filter((m) => m.content.trim())
      .slice(-ANON_HISTORY_TURNS)
      .map((m) => ({ role: m.role, content: m.content.slice(0, 800) }));

    setInput('');
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: question },
      { role: 'assistant', content: '' },
    ]);
    setStreaming(true);

    try {
      let response = await postQuestion(question, priorTurns, authed);

      // A cookie that has gone stale should downgrade the helper, not break it.
      if (response.status === 401 && authed) {
        setAuthed(false);
        response = await postQuestion(question, priorTurns, false);
      }

      if (response.status === 429) {
        const detail = await response
          .json()
          .then((b) => b?.detail as string)
          .catch(() => null);
        replaceLast(
          detail ??
            'That is as many questions as I can answer right now. Try again shortly.',
        );
        return;
      }

      if (!response.ok || !response.body) {
        replaceLast('The tutor is unreachable right now. Is the backend running?');
        setUnreachable(true);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let answer = '';
      let sources: ChatSource[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE frames are separated by a blank line; keep any partial tail.
        const chunks = buffer.split('\n\n');
        buffer = chunks.pop() ?? '';

        for (const frame of chunks) {
          const line = frame.split('\n').find((l) => l.startsWith('data: '));
          if (!line) continue;
          let event: {
            type: string;
            text?: string;
            sources?: ChatSource[];
            degraded?: boolean;
            action?: string;
            detail?: { concept_name?: string; week_no?: number };
          };
          try {
            event = JSON.parse(line.slice(6));
          } catch {
            continue;
          }

          if (event.type === 'sources') {
            sources = event.sources ?? [];
            if (typeof event.degraded === 'boolean') setDegraded(event.degraded);
          } else if (event.type === 'token') {
            answer += event.text ?? '';
            replaceLast(answer, sources);
          } else if (event.type === 'action' && event.action === 'roadmap_updated') {
            const detail = event.detail;
            setRoadmapAction(
              detail?.concept_name
                ? `Added "${detail.concept_name}" to Week ${detail.week_no}`
                : 'Roadmap updated',
            );
            router.refresh();
            setTimeout(() => setRoadmapAction(null), 5000);
          }
        }
      }

      if (!answer) replaceLast('No answer came back. Try rephrasing the question.');
    } catch {
      replaceLast('Lost connection to the tutor.');
    } finally {
      setStreaming(false);
    }
  }

  function postQuestion(
    question: string,
    priorTurns: { role: string; content: string }[],
    asLearner: boolean,
  ) {
    const body = asLearner
      ? { message: question, context: toPayload(resolved) }
      : {
          message: question.slice(0, 600),
          context: toPayload(resolved),
          // Anonymous conversations are not stored anywhere, so continuity
          // means replaying what this tab already has.
          history: priorTurns,
        };

    return fetch(asLearner ? '/api/chat' : '/api/chat/public', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  async function clearConversation() {
    setMessages([]);
    if (!authed) return;
    try {
      await fetch('/api/chat/history', { method: 'DELETE' });
    } catch {
      // Local state is already cleared; the server copy can wait.
    }
  }

  const suggestions =
    opening?.suggestions?.length ? opening.suggestions : FALLBACK_SUGGESTIONS;

  const subtitle = unreachable
    ? 'Cannot reach the service'
    : degraded
      ? 'Model offline — answering from the notes'
      : authed
        ? 'Grounded in your roadmap'
        : 'Ask about SkillAtlas — no account needed';

  return (
    <div className="fixed right-5 bottom-5 z-50 print:hidden">
      {open && (
        <div className="mb-3 flex h-[32rem] w-[min(24rem,calc(100vw-2.5rem))] flex-col overflow-hidden rounded-lg border bg-background shadow-2xl">
          <header className="flex items-center justify-between gap-2 border-b bg-card px-4 py-3">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold">
                {authed ? 'AI Tutor' : 'SkillAtlas Helper'}
              </h2>
              <p className="truncate text-xs text-muted-foreground">{subtitle}</p>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={clearConversation}
                aria-label="Clear conversation"
                title="Clear conversation"
              >
                <Trash2 />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => setOpen(false)}
                aria-label="Close tutor"
              >
                <X />
              </Button>
            </div>
          </header>

          {unreachable && (
            <p className="flex items-start gap-2 border-b bg-destructive/10 px-4 py-2 text-xs text-destructive">
              <PlugZap className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              The SkillAtlas API is not responding, so there is nothing to ask
              right now. Nothing you type would be answered.
            </p>
          )}

          {!unreachable && degraded && (
            <p className="flex items-start gap-2 border-b bg-accent px-4 py-2 text-xs text-accent-foreground">
              <WifiOff className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              The language model is not running, so answers are excerpts from the
              course notes rather than generated{authed ? (
                <>
                  {' '}
                  — start it with <code>ollama serve</code>
                </>
              ) : null}
              .
            </p>
          )}

          {roadmapAction && (
            <div className="flex items-center gap-2 border-b bg-emerald-500/10 px-4 py-2 text-xs text-emerald-400 animate-in slide-in-from-top-2">
              <CheckCircle className="h-3.5 w-3.5 shrink-0" />
              {roadmapAction}
            </div>
          )}

          <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto bg-muted/20 p-4">
            {messages.length === 0 && (
              <div>
                <p className="flex items-start gap-2 text-sm text-muted-foreground">
                  <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <span>
                    {opening?.greeting ??
                      'Ask about anything in the SkillAtlas catalogue.'}
                  </span>
                </p>
                <div className="mt-4 space-y-2">
                  {suggestions.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      disabled={unreachable}
                      onClick={() => send(suggestion)}
                      className="block w-full rounded-lg border bg-background px-3 py-2 text-left text-sm transition-colors hover:border-primary hover:text-primary disabled:opacity-50"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
                {!authed && !unreachable && (
                  <p className="mt-4 text-xs text-muted-foreground">
                    Signed out, so I cannot see any progress or account — and
                    there is a limit on how much I will answer.{' '}
                    <a className="underline hover:text-primary" href="/signup">
                      Sign up
                    </a>{' '}
                    for a tutor that knows your route.
                  </p>
                )}
              </div>
            )}

            {messages.map((message, index) => (
              <div
                key={index}
                className={cn(
                  'max-w-[88%] rounded-xl px-3 py-2 text-sm',
                  message.role === 'user'
                    ? 'ml-auto rounded-br-sm bg-primary text-primary-foreground'
                    : 'rounded-bl-sm border bg-background',
                )}
              >
                {message.role === 'assistant' ? (
                  message.content ? (
                    <>
                      <Markdown className="space-y-2 [&_p]:text-sm">
                        {message.content}
                      </Markdown>
                      {message.sources && message.sources.length > 0 && (
                        <p className="mt-3 border-t pt-2 text-xs text-muted-foreground">
                          Based on: {message.sources.map((s) => s.name).join(', ')}
                        </p>
                      )}
                    </>
                  ) : (
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  )
                ) : (
                  message.content
                )}
              </div>
            ))}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex gap-2 border-t bg-background p-3"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                unreachable
                  ? 'The tutor service is offline'
                  : authed
                    ? 'Ask about your roadmap…'
                    : 'Ask about SkillAtlas…'
              }
              aria-label="Message the tutor"
              maxLength={authed ? 4000 : 600}
              disabled={streaming || unreachable}
              className="min-w-0 flex-1 rounded-full border bg-muted px-4 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
            />
            <Button
              type="submit"
              size="icon"
              disabled={streaming || unreachable || !input.trim()}
              aria-label="Send"
            >
              {streaming ? <Loader2 className="animate-spin" /> : <Send />}
            </Button>
          </form>
        </div>
      )}

      <Button
        size="icon-lg"
        className="h-14 w-14 rounded-full shadow-xl"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? 'Close AI tutor' : 'Open AI tutor'}
        aria-expanded={open}
      >
        {open ? <X className="size-6" /> : <MessageSquare className="size-6" />}
      </Button>
    </div>
  );
}
