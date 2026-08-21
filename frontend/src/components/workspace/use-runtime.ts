'use client';

/**
 * One hook over three very different runtimes.
 *
 * The workspace calls `run(files, tests)` and gets a `RunResult` back; whether
 * that meant booting a 13MB Python interpreter, an in-memory SQLite, or
 * writing a document into an iframe is not its problem.
 *
 * `stop()` is the reason the worker-based runtimes exist at all: terminating
 * and re-creating a worker is the only reliable way to interrupt a runaway
 * loop, and a learner writing one is a matter of when, not if.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import type { RunRequest, RunResult, RuntimeTest, WorkerMessage, WorkspaceFile } from './runtime-protocol';
import { runInFrame } from './web-runtime';

export type RuntimeStatus = 'booting' | 'ready' | 'running' | 'error';

type Options = {
  runtime: 'python' | 'web' | 'sql';
  entryPath: string;
  /** Required for `web`; ignored otherwise. */
  frameRef?: React.RefObject<HTMLIFrameElement | null>;
};

function createWorker(runtime: 'python' | 'sql'): Worker {
  // Classic workers, and not really a choice: Turbopack bootstraps every worker
  // with a classic stub that pulls the compiled chunks in with importScripts,
  // so `{ type: 'module' }` here changes nothing. sql.js wants that anyway —
  // it ships only a UMD bundle. Pyodide 0.28+ refuses to boot in a classic
  // worker, which pyodide.worker.ts deals with on its own side.
  //
  // The URL must be a static `new URL(..., import.meta.url)` for the bundler
  // to emit the chunk.
  return runtime === 'python'
    ? new Worker(new URL('./pyodide.worker.ts', import.meta.url))
    : new Worker(new URL('./sql.worker.ts', import.meta.url));
}

export function useRuntime({ runtime, entryPath, frameRef }: Options) {
  const [status, setStatus] = useState<RuntimeStatus>(runtime === 'web' ? 'ready' : 'booting');
  const [bootError, setBootError] = useState<string | null>(null);

  const workerRef = useRef<Worker | null>(null);
  const pendingRef = useRef<((result: RunResult) => void) | null>(null);
  const runCounter = useRef(0);

  const spawn = useCallback(() => {
    if (runtime === 'web') return;

    const worker = createWorker(runtime);
    worker.addEventListener('message', (event: MessageEvent<WorkerMessage>) => {
      const message = event.data;
      if (message.type === 'ready') {
        setStatus((current) => (current === 'running' ? current : 'ready'));
      } else if (message.type === 'result') {
        pendingRef.current?.(message.result);
        pendingRef.current = null;
        setStatus('ready');
      } else {
        setBootError(message.message);
        setStatus('error');
        pendingRef.current = null;
      }
    });
    workerRef.current = worker;
  }, [runtime]);

  useEffect(() => {
    spawn();
    return () => {
      workerRef.current?.terminate();
      workerRef.current = null;
    };
  }, [spawn]);

  const stop = useCallback(() => {
    if (runtime === 'web') {
      // Blanking the frame kills whatever is looping inside it.
      if (frameRef?.current) frameRef.current.srcdoc = '';
    } else {
      workerRef.current?.terminate();
      workerRef.current = null;
      setStatus('booting');
      spawn();
    }
    pendingRef.current?.({
      runId: 'stopped',
      output: '',
      error: 'Stopped.',
      tests: [],
      durationMs: 0,
    });
    pendingRef.current = null;
  }, [frameRef, runtime, spawn]);

  const run = useCallback(
    async (files: WorkspaceFile[], tests: RuntimeTest[]): Promise<RunResult> => {
      runCounter.current += 1;
      const request: RunRequest = {
        runId: `run-${runCounter.current}`,
        files,
        entryPath,
        tests,
      };
      setStatus('running');

      if (runtime === 'web') {
        const frame = frameRef?.current;
        if (!frame) {
          setStatus('error');
          return { runId: request.runId, output: '', error: 'No preview frame.', tests: [], durationMs: 0 };
        }
        const result = await runInFrame(frame, request);
        setStatus('ready');
        return result;
      }

      if (!workerRef.current) spawn();
      return new Promise<RunResult>((resolve) => {
        pendingRef.current = resolve;
        workerRef.current?.postMessage(request);
      });
    },
    [entryPath, frameRef, runtime, spawn],
  );

  return { status, bootError, run, stop };
}
