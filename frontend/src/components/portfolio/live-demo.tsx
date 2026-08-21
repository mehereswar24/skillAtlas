'use client';

/**
 * The part of a portfolio that nothing else does: the project actually runs.
 *
 * The learner's passing submission is shipped with the page, and this boots
 * the same in-browser runtime the workspace uses — Pyodide, sql.js, or a
 * sandboxed iframe — in the *visitor's* browser. A recruiter can press Run and
 * watch the tests go green, which is a materially different claim from a
 * screenshot.
 *
 * Two deliberate constraints:
 *
 * - **Nothing boots until asked.** `useRuntime` spawns its worker on mount,
 *   and Pyodide is a ~13MB download. So the hook lives in `DemoRunner`, which
 *   is only mounted once the visitor clicks Run. A profile with six Python
 *   projects costs nothing until one is opened.
 * - **The code is read-only.** This is a record of what was shipped. Editing
 *   it belongs in the workspace, behind an account.
 */

import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, Loader2, Play, Square, XCircle } from 'lucide-react';

import { CodeEditor } from '@/components/workspace/code-editor';
import type { RunResult, WorkspaceFile } from '@/components/workspace/runtime-protocol';
import { RUNTIME_LABELS } from '@/components/workspace/runtime-protocol';
import { useRuntime } from '@/components/workspace/use-runtime';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

import type { PublicProject } from './types';

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

export function LiveDemo({ project }: { project: PublicProject }) {
  const [armed, setArmed] = useState(false);
  const runnable = project.files.length > 0 && project.entry_path !== null;

  if (!runnable) {
    return (
      <p className="rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">
        {project.title} was built and passed here, but its author kept the source
        private.
      </p>
    );
  }

  if (!armed) {
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/30 px-3 py-2.5">
        <Button size="sm" onClick={() => setArmed(true)}>
          <Play />
          Run it
        </Button>
        <p className="min-w-0 flex-1 text-xs text-muted-foreground">
          Runs {RUNTIME_LABELS[project.runtime] ?? project.runtime} in your browser —
          nothing is sent to a server.
        </p>
      </div>
    );
  }

  return <DemoRunner project={project} />;
}

function DemoRunner({ project }: { project: PublicProject }) {
  const dark = useIsDark();
  const frameRef = useRef<HTMLIFrameElement | null>(null);
  const [result, setResult] = useState<RunResult | null>(null);
  const [activePath, setActivePath] = useState(
    project.entry_path ?? project.files[0]?.path ?? '',
  );
  const started = useRef(false);
  const alive = useRef(true);

  const { status, bootError, run, stop } = useRuntime({
    runtime: project.runtime,
    entryPath: project.entry_path ?? project.files[0]?.path ?? '',
    frameRef,
  });

  const files: WorkspaceFile[] = project.files.map((file) => ({
    path: file.path,
    content: file.content,
  }));

  // Run once, as soon as the runtime is up — the visitor already asked for it
  // by mounting this component, so making them press a second button would be
  // a pointless step.
  //
  // The "is it still alive?" flag is a ref rather than a local `let` closed
  // over by the cleanup, and that is the whole trick: `run()` sets status to
  // 'running' synchronously, which changes this effect's dependency, which
  // runs its cleanup — while the promise it started is still in flight. A
  // local flag would be flipped by that cleanup and the result thrown away,
  // leaving the panel blank forever.
  useEffect(() => {
    if (started.current || status !== 'ready') return;
    started.current = true;
    run(files, project.tests).then((outcome) => {
      if (alive.current) setResult(outcome);
    });
    // `files` is rebuilt every render from immutable props; depending on it
    // would re-run on every state change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  // `alive` is re-armed in the body, not just at `useRef(true)`. React Strict
  // Mode mounts, unmounts and mounts again in development; without this the
  // simulated unmount would leave the ref false for the rest of the component's
  // life and every result would be silently discarded.
  //
  // `started` is deliberately *not* reset here. It survives the simulated
  // unmount so the remount does not fire a second run on top of the first —
  // which, for the iframe runtime, means writing a new document into the frame
  // while the previous run is still waiting on it, and getting an 8-second
  // timeout that overwrites a perfectly good green result with zeros.
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const busy = status === 'running';
  const passed = result?.tests.filter((test) => test.passed).length ?? 0;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2">
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
          {status === 'booting'
            ? `Starting ${RUNTIME_LABELS[project.runtime] ?? project.runtime}…`
            : status === 'running'
              ? 'Running'
              : status === 'error'
                ? 'Runtime failed'
                : 'Ready'}
        </span>

        <div className="ml-auto flex items-center gap-2">
          {busy ? (
            <Button variant="outline" size="sm" onClick={stop}>
              <Square />
              Stop
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              disabled={status === 'booting'}
              onClick={async () => setResult(await run(files, project.tests))}
            >
              {status === 'booting' ? <Loader2 className="animate-spin" /> : <Play />}
              Run again
            </Button>
          )}
        </div>
      </div>

      {bootError && (
        <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {bootError}
        </p>
      )}

      {project.runtime === 'web' && (
        <iframe
          ref={frameRef}
          title={`${project.title} preview`}
          // No allow-same-origin: an opaque origin means the embedded project
          // cannot reach this page, its cookies, or the API. A portfolio runs
          // a stranger's code in a visitor's browser, so this is load-bearing.
          sandbox="allow-scripts"
          className="h-64 w-full rounded-lg border bg-white"
        />
      )}

      {result && (
        <div className="grid gap-3 lg:grid-cols-2">
          <section>
            <h4 className="mb-1.5 text-xs font-semibold text-muted-foreground">Output</h4>
            <pre className="h-36 overflow-auto rounded-lg border bg-muted/40 p-2.5 font-mono text-[11px] whitespace-pre-wrap">
              {result.error ? (
                <span className="text-destructive">{result.error}</span>
              ) : (
                result.output || <span className="text-muted-foreground">Nothing printed.</span>
              )}
            </pre>
          </section>

          {project.tests.length > 0 && (
            <section>
              <h4 className="mb-1.5 flex items-center justify-between text-xs font-semibold text-muted-foreground">
                <span>Tests, re-run just now</span>
                <span className="tabular-nums">
                  {passed} / {project.tests.length} passing
                </span>
              </h4>
              <ul className="h-36 space-y-1 overflow-auto rounded-lg border p-2">
                {result.tests.map((test) => (
                  <li key={test.testId} className="flex items-start gap-2 px-1 py-0.5 text-xs">
                    {test.passed ? (
                      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
                    ) : (
                      <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-destructive" />
                    )}
                    <span className={cn('min-w-0', test.passed && 'text-muted-foreground')}>
                      {test.name}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}

      <details className="rounded-lg border">
        <summary className="cursor-pointer px-3 py-2 text-xs font-medium">
          Read the code
        </summary>
        <div className="border-t">
          <nav aria-label="Files" className="flex flex-wrap gap-1 border-b bg-muted/30 p-1.5">
            {project.files.map((file) => (
              <button
                key={file.path}
                type="button"
                onClick={() => setActivePath(file.path)}
                aria-current={file.path === activePath ? 'true' : undefined}
                className={cn(
                  'rounded px-2 py-1 font-mono text-[11px] transition-colors',
                  file.path === activePath
                    ? 'bg-secondary text-foreground'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {file.path}
              </button>
            ))}
          </nav>
          <div className="max-h-80 overflow-auto">
            <CodeEditor
              path={activePath}
              value={project.files.find((f) => f.path === activePath)?.content ?? ''}
              onChange={() => {}}
              readOnly
              dark={dark}
            />
          </div>
        </div>
      </details>
    </div>
  );
}
