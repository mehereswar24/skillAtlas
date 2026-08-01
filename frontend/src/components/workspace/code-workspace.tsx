'use client';

/**
 * The build environment: files on the left, editor in the middle, output and
 * test results below.
 *
 * Two decisions worth knowing about:
 *
 * - Drafts autosave to localStorage per project. Losing an hour of work to a
 *   refresh is the fastest way to make someone never open the editor again.
 * - Tests run in the learner's browser, so the pass/fail signal is reported by
 *   the client. The server records the submission and re-checks what it can,
 *   but it cannot re-run the code. The results panel says so rather than
 *   implying an authority it does not have.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  CircleDashed,
  Loader2,
  Play,
  RotateCcw,
  Send,
  Square,
  Trophy,
  XCircle,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Markdown } from '@/components/markdown';
import { cn } from '@/lib/utils';
import type { ProjectDetail, SubmissionResult } from '@/lib/types';

import { CodeEditor } from './code-editor';
import type { RunResult, WorkspaceFile } from './runtime-protocol';
import { useRuntime } from './use-runtime';

const draftKey = (slug: string) => `skillatlas-draft:${slug}`;

function useIsDark() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const root = document.documentElement;
    const sync = () => setDark(root.classList.contains('dark'));
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);
  return dark;
}

export function CodeWorkspace({ project }: { project: ProjectDetail }) {
  const router = useRouter();
  const dark = useIsDark();
  const frameRef = useRef<HTMLIFrameElement | null>(null);

  const starter = useMemo(
    () => Object.fromEntries(project.files.map((file) => [file.path, file.content])),
    [project.files],
  );
  const entryPath = useMemo(
    () => project.files.find((file) => file.is_entry)?.path ?? project.files[0]?.path ?? '',
    [project.files],
  );

  const [contents, setContents] = useState<Record<string, string>>(starter);
  const [activePath, setActivePath] = useState(entryPath);
  const [result, setResult] = useState<RunResult | null>(null);
  const [submission, setSubmission] = useState<SubmissionResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const { status, bootError, run, stop } = useRuntime({
    runtime: project.runtime as 'python' | 'web' | 'sql',
    entryPath,
    frameRef,
  });

  // Restore any draft once, on mount.
  useEffect(() => {
    try {
      const saved = localStorage.getItem(draftKey(project.slug));
      if (saved) setContents({ ...starter, ...JSON.parse(saved) });
    } catch {
      // A corrupt draft is not worth an error message; the starter is fine.
    }
  }, [project.slug, starter]);

  const editable = useMemo(
    () => project.files.filter((file) => !file.is_readonly).map((file) => file.path),
    [project.files],
  );

  useEffect(() => {
    const draft = Object.fromEntries(editable.map((path) => [path, contents[path] ?? '']));
    const timer = setTimeout(() => {
      try {
        localStorage.setItem(draftKey(project.slug), JSON.stringify(draft));
      } catch {
        // Quota exceeded or storage disabled — not worth interrupting for.
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [contents, editable, project.slug]);

  const files: WorkspaceFile[] = useMemo(
    () => project.files.map((file) => ({ path: file.path, content: contents[file.path] ?? '' })),
    [contents, project.files],
  );

  const busy = status === 'running';

  const doRun = useCallback(
    async (withTests: boolean) => {
      setSubmission(null);
      setSubmitError(null);
      const outcome = await run(files, withTests ? project.tests : []);
      setResult(outcome);
    },
    [files, project.tests, run],
  );

  const allPassed =
    result !== null &&
    result.tests.length === project.tests.length &&
    project.tests.length > 0 &&
    result.tests.every((test) => test.passed);

  async function submit() {
    if (!result) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const response = await fetch(`/api/projects/${project.slug}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          files: files.map((file) => ({ path: file.path, content: file.content })),
          results: result.tests.map((test) => ({ test_id: test.testId, passed: test.passed })),
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setSubmitError(data.detail ?? 'Could not record your submission.');
        return;
      }
      setSubmission(data as SubmissionResult);
      router.refresh();
    } catch {
      setSubmitError('Could not reach the server. Is the backend running?');
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setContents(starter);
    setResult(null);
    setSubmission(null);
    localStorage.removeItem(draftKey(project.slug));
  }

  const activeFile = project.files.find((file) => file.path === activePath);

  return (
    <div className="space-y-4">
      {/* --- toolbar ------------------------------------------------- */}
      <div className="flex flex-wrap items-center gap-2 rounded-xl border bg-card px-3 py-2">
        <RuntimeStatusPill status={status} runtime={project.runtime} />

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Button variant="ghost" size="sm" onClick={reset} disabled={busy}>
            <RotateCcw />
            Reset
          </Button>
          {busy ? (
            <Button variant="outline" size="sm" onClick={stop}>
              <Square />
              Stop
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={() => doRun(false)} disabled={status === 'booting'}>
              <Play />
              Run
            </Button>
          )}
          <Button size="sm" onClick={() => doRun(true)} disabled={busy || status === 'booting'}>
            {busy ? <Loader2 className="animate-spin" /> : <CheckCircle2 />}
            Run tests
          </Button>
        </div>
      </div>

      {bootError && (
        <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {bootError}
        </p>
      )}

      {/* --- files + editor ------------------------------------------ */}
      <div className="grid gap-4 lg:grid-cols-[180px_minmax(0,1fr)]">
        <nav aria-label="Project files" className="space-y-1">
          {project.files.map((file) => (
            <button
              key={file.path}
              type="button"
              onClick={() => setActivePath(file.path)}
              aria-current={file.path === activePath ? 'true' : undefined}
              className={cn(
                'flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left font-mono text-xs transition-colors',
                file.path === activePath
                  ? 'bg-secondary text-foreground'
                  : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
              )}
            >
              <ChevronRight className={cn('h-3 w-3 shrink-0', file.path === activePath ? 'text-primary' : 'opacity-0')} />
              <span className="truncate">{file.path}</span>
              {file.is_readonly && (
                <span className="ml-auto shrink-0 rounded bg-muted px-1 text-[10px] tracking-wide text-muted-foreground uppercase">
                  read
                </span>
              )}
            </button>
          ))}
        </nav>

        <div className="min-w-0 overflow-hidden rounded-xl border">
          {activeFile?.is_readonly && (
            <p className="border-b bg-muted/50 px-3 py-1.5 text-xs text-muted-foreground">
              Provided for you — read it, but edit {entryPath}.
            </p>
          )}
          <div className="h-[420px] overflow-auto">
            {activeFile && (
              <CodeEditor
                path={activeFile.path}
                value={contents[activeFile.path] ?? ''}
                onChange={(next) => setContents((prev) => ({ ...prev, [activeFile.path]: next }))}
                readOnly={activeFile.is_readonly}
                dark={dark}
              />
            )}
          </div>
        </div>
      </div>

      {/* --- preview (web only) -------------------------------------- */}
      {project.runtime === 'web' && (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-muted-foreground">Preview</h3>
          <iframe
            ref={frameRef}
            title="Project preview"
            // No allow-same-origin: the frame gets an opaque origin and cannot
            // reach this page, its cookies, or the API.
            sandbox="allow-scripts"
            className="h-72 w-full rounded-xl border bg-white"
          />
        </section>
      )}

      {/* --- output and results -------------------------------------- */}
      {result && <ResultsPanel result={result} testCount={project.tests.length} tests={project.tests} />}

      {/* --- submit --------------------------------------------------- */}
      {result && !submission && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-4">
          <div className="min-w-0 flex-1 text-sm">
            {allPassed ? (
              <p className="font-medium text-success">
                Every test passes. Submit to bank {project.xp_reward} points.
              </p>
            ) : (
              <p className="text-muted-foreground">
                Submitting records the attempt. Points are awarded once every test passes.
              </p>
            )}
            {submitError && (
              <p role="alert" className="mt-1 text-destructive">
                {submitError}
              </p>
            )}
          </div>
          <Button onClick={submit} disabled={submitting} variant={allPassed ? 'default' : 'outline'}>
            {submitting ? <Loader2 className="animate-spin" /> : <Send />}
            {submitting ? 'Submitting…' : 'Submit'}
          </Button>
        </div>
      )}

      {submission && <SubmissionSummary submission={submission} xpReward={project.xp_reward} />}
    </div>
  );
}

function RuntimeStatusPill({ status, runtime }: { status: string; runtime: string }) {
  const label =
    status === 'booting'
      ? runtime === 'python'
        ? 'Starting Python…'
        : 'Starting…'
      : status === 'running'
        ? 'Running'
        : status === 'error'
          ? 'Runtime failed'
          : 'Ready';

  return (
    <span className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
      <span
        className={cn(
          'h-2 w-2 rounded-full',
          status === 'ready' && 'bg-success',
          status === 'running' && 'animate-pulse bg-primary',
          status === 'booting' && 'animate-pulse bg-muted-foreground',
          status === 'error' && 'bg-destructive',
        )}
        aria-hidden
      />
      {label}
    </span>
  );
}

function ResultsPanel({
  result,
  testCount,
  tests,
}: {
  result: RunResult;
  testCount: number;
  tests: ProjectDetail['tests'];
}) {
  const passed = result.tests.filter((test) => test.passed).length;
  const hiddenById = new Map(tests.map((test) => [test.id, test.is_hidden]));

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section>
        <h3 className="mb-2 text-sm font-semibold text-muted-foreground">Output</h3>
        <pre className="h-44 overflow-auto rounded-xl border bg-muted/40 p-3 font-mono text-xs whitespace-pre-wrap">
          {result.error ? (
            <span className="text-destructive">{result.error}</span>
          ) : (
            result.output || <span className="text-muted-foreground">Nothing printed.</span>
          )}
        </pre>
      </section>

      {testCount > 0 && (
        <section>
          <h3 className="mb-2 flex items-center justify-between text-sm font-semibold text-muted-foreground">
            <span>Tests</span>
            <span className="tabular-nums">
              {passed} / {testCount} passing
            </span>
          </h3>
          <ul className="h-44 space-y-1.5 overflow-auto rounded-xl border p-2">
            {result.tests.length === 0 && (
              <li className="px-1 py-2 text-sm text-muted-foreground">
                No tests ran. Use “Run tests”.
              </li>
            )}
            {result.tests.map((test) => (
              <li key={test.testId} className="rounded-lg px-2 py-1.5 text-sm">
                <span className="flex items-start gap-2">
                  {test.passed ? (
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                  ) : (
                    <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                  )}
                  <span className="min-w-0">
                    <span className={cn(test.passed && 'text-muted-foreground')}>{test.name}</span>
                    {hiddenById.get(test.testId) && (
                      <span className="ml-2 rounded bg-muted px-1 text-[10px] tracking-wide text-muted-foreground uppercase">
                        hidden
                      </span>
                    )}
                    {!test.passed && test.message && (
                      <span className="mt-1 block font-mono text-xs break-words text-destructive">
                        {test.message}
                      </span>
                    )}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function SubmissionSummary({
  submission,
  xpReward,
}: {
  submission: SubmissionResult;
  xpReward: number;
}) {
  return (
    <div
      className={cn(
        'rounded-xl border p-5',
        submission.passed ? 'border-success/40 bg-success/5' : 'bg-card',
      )}
    >
      <div className="flex items-start gap-3">
        {submission.passed ? (
          <Trophy className="mt-0.5 h-5 w-5 shrink-0 text-success" />
        ) : (
          <CircleDashed className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
        )}
        <div className="min-w-0 flex-1">
          <h3 className="font-display text-lg font-semibold">
            {submission.passed
              ? submission.xp_earned > 0
                ? `Shipped — ${submission.xp_earned} points`
                : 'Shipped again'
              : `${submission.submission.passed_count} of ${submission.submission.total_count} tests passing`}
          </h3>

          {submission.passed && submission.xp_earned === 0 && (
            <p className="mt-1 text-sm text-muted-foreground">
              You already banked the {xpReward} points for this one — resubmitting keeps the
              record but does not pay twice.
            </p>
          )}

          {submission.rejected_reason && (
            <p className="mt-2 flex items-start gap-2 text-sm text-warning">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{submission.rejected_reason}</span>
            </p>
          )}

          {submission.new_badges.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {submission.new_badges.map((badge) => (
                <span
                  key={badge.slug}
                  className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary"
                >
                  {badge.name}
                </span>
              ))}
            </div>
          )}

          <p className="mt-3 text-xs text-muted-foreground">
            Tests run in your browser, so this result is self-reported. We keep the code you
            submitted and check what we can from here.
          </p>

          {submission.solution_md && (
            <details className="mt-4 rounded-lg border bg-background p-3">
              <summary className="cursor-pointer text-sm font-medium">
                How we would have written it
              </summary>
              <Markdown className="mt-3 text-sm">{submission.solution_md}</Markdown>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}
