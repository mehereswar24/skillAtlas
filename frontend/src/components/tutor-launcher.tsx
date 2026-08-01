'use client';

import { useEffect, useRef, useState } from 'react';
import { Loader2, MessageSquare, Send, Trash2, WifiOff, X } from 'lucide-react';

import { Markdown } from '@/components/markdown';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { ChatMessage, ChatSource } from '@/lib/types';

const SUGGESTIONS = [
  'What should I learn next?',
  'Explain this concept in simpler terms',
  'How would this come up in an interview?',
];

/**
 * Floating AI tutor.
 *
 * Consumes the backend's SSE stream through the same-origin BFF, so tokens
 * appear as they are generated. When Ollama is not running the stream still
 * arrives — flagged as degraded — and the panel says so rather than showing a
 * generic failure.
 */
export function TutorLauncher({ conceptSlug }: { conceptSlug?: string }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [degraded, setDegraded] = useState(false);
  const [loadedHistory, setLoadedHistory] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open || loadedHistory) return;
    setLoadedHistory(true);
    (async () => {
      const [historyRes, statusRes] = await Promise.all([
        fetch('/api/chat/history?limit=20'),
        fetch('/api/chat/status'),
      ]);
      if (statusRes.ok) setDegraded(!(await statusRes.json()).available);
      if (historyRes.ok) {
        const rows = await historyRes.json();
        setMessages(
          rows.map((row: { role: string; content: string }) => ({
            role: row.role as ChatMessage['role'],
            content: row.content,
          })),
        );
      }
    })();
  }, [open, loadedHistory]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, open]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || streaming) return;

    setInput('');
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: question },
      { role: 'assistant', content: '' },
    ]);
    setStreaming(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: question, concept_slug: conceptSlug ?? null }),
      });

      if (!response.ok || !response.body) {
        replaceLast('The tutor is unreachable right now. Is the backend running?');
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
        const frames = buffer.split('\n\n');
        buffer = frames.pop() ?? '';

        for (const frame of frames) {
          const line = frame.split('\n').find((l) => l.startsWith('data: '));
          if (!line) continue;
          let event: { type: string; text?: string; sources?: ChatSource[]; degraded?: boolean };
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

  function replaceLast(content: string, sources?: ChatSource[]) {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last?.role === 'assistant') {
        next[next.length - 1] = { ...last, content, sources };
      }
      return next;
    });
  }

  async function clearHistory() {
    await fetch('/api/chat/history', { method: 'DELETE' });
    setMessages([]);
  }

  return (
    <div className="fixed right-5 bottom-5 z-50 print:hidden">
      {open && (
        <div className="mb-3 flex h-[32rem] w-[min(24rem,calc(100vw-2.5rem))] flex-col overflow-hidden rounded-lg border bg-background shadow-2xl">
          <header className="flex items-center justify-between gap-2 border-b bg-card px-4 py-3">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold">AI Tutor</h2>
              <p className="truncate text-xs text-muted-foreground">
                {degraded ? 'Offline — answering from your notes' : 'Grounded in your roadmap'}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={clearHistory}
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

          {degraded && (
            <p className="flex items-start gap-2 border-b bg-accent px-4 py-2 text-xs text-accent-foreground">
              <WifiOff className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              Ollama is not running, so answers are excerpts from your course notes
              rather than generated. Start it with <code>ollama serve</code>.
            </p>
          )}

          <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto bg-muted/20 p-4">
            {messages.length === 0 && (
              <div>
                <p className="text-sm text-muted-foreground">
                  Ask about anything on your roadmap. I can see what you have finished
                  and what is next.
                </p>
                <div className="mt-4 space-y-2">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => send(suggestion)}
                      className="block w-full rounded-lg border bg-background px-3 py-2 text-left text-sm transition-colors hover:border-primary hover:text-primary"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
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
              placeholder="Ask about your roadmap…"
              aria-label="Message the tutor"
              disabled={streaming}
              className="min-w-0 flex-1 rounded-full border bg-muted px-4 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
            />
            <Button
              type="submit"
              size="icon"
              disabled={streaming || !input.trim()}
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
