/**
 * Runs HTML/CSS/JS projects inside a sandboxed iframe.
 *
 * Unlike Python and SQL this cannot live in a worker — the whole point is that
 * there is a document to assert against. The isolation instead comes from
 * `sandbox="allow-scripts"` with no `allow-same-origin`: the frame gets an
 * opaque origin, so learner code cannot read our cookies, call our API, or
 * touch the page around it.
 *
 * That opaque origin is also why the message handler checks a per-run nonce
 * instead of `event.origin` — a sandboxed frame posts from the string "null",
 * which every other frame on the internet can also claim.
 */

import type { RunRequest, RunResult, TestOutcome } from './runtime-protocol';

/** Long enough for a slow first paint, short enough to notice a hang. */
const TIMEOUT_MS = 8000;

type FramePayload = {
  nonce: string;
  logs: string[];
  error: string | null;
  results: { id: number; passed: boolean; message: string | null }[];
};

function buildDocument(request: RunRequest, nonce: string): string {
  const file = (path: string) => request.files.find((f) => f.path === path)?.content ?? '';
  const html = file(request.entryPath) || file('index.html');
  const css = request.files.filter((f) => f.path.endsWith('.css')).map((f) => f.content).join('\n');
  const js = request.files
    .filter((f) => f.path.endsWith('.js') && f.path !== request.entryPath)
    .map((f) => f.content)
    .join('\n;\n');

  const assertions = request.tests.map((test) => ({ id: test.id, code: test.code }));

  // The harness runs after the learner's script, reports once, and swallows
  // nothing: an error in their code still produces a result rather than a
  // silent timeout.
  const harness = `
<script>
(function () {
  var logs = [];
  ['log', 'info', 'warn', 'error'].forEach(function (level) {
    var original = console[level];
    console[level] = function () {
      logs.push(Array.prototype.map.call(arguments, String).join(' '));
      original.apply(console, arguments);
    };
  });

  var fatal = null;
  window.addEventListener('error', function (event) {
    fatal = fatal || String(event.message);
  });

  function report() {
    var results = [];
    ${JSON.stringify(assertions)}.forEach(function (test) {
      try {
        var passed = !!eval(test.code);
        results.push({ id: test.id, passed: passed, message: passed ? null : 'returned a falsy value' });
      } catch (error) {
        results.push({ id: test.id, passed: false, message: String(error && error.message || error) });
      }
    });
    parent.postMessage({
      nonce: ${JSON.stringify(nonce)},
      logs: logs,
      error: fatal,
      results: results,
    }, '*');
  }

  // One frame after load, so code that renders on DOMContentLoaded has run.
  if (document.readyState === 'complete') requestAnimationFrame(report);
  else window.addEventListener('load', function () { requestAnimationFrame(report); });
})();
</script>`;

  const head = `<style>${css}</style>`;
  const body = `<script>${js}</script>${harness}`;

  if (/<\/head>/i.test(html) && /<\/body>/i.test(html)) {
    return html.replace(/<\/head>/i, `${head}</head>`).replace(/<\/body>/i, `${body}</body>`);
  }
  return `<!doctype html><html><head><meta charset="utf-8">${head}</head><body>${html}${body}</body></html>`;
}

/**
 * Render `request` into `frame` and resolve once the harness reports.
 *
 * The caller owns the iframe so the preview stays on screen after the run —
 * seeing the thing you built is half the point.
 */
export function runInFrame(frame: HTMLIFrameElement, request: RunRequest): Promise<RunResult> {
  const started = Date.now();
  const nonce = `${request.runId}-${Math.random().toString(36).slice(2)}`;

  return new Promise((resolve) => {
    let settled = false;

    const finish = (payload: FramePayload | null, timedOut: boolean) => {
      if (settled) return;
      settled = true;
      window.removeEventListener('message', onMessage);
      clearTimeout(timer);

      const byId = new Map((payload?.results ?? []).map((r) => [r.id, r]));
      const tests: TestOutcome[] = request.tests.map((test) => {
        const outcome = byId.get(test.id);
        return {
          testId: test.id,
          name: test.name,
          passed: outcome?.passed ?? false,
          message: outcome?.message ?? (timedOut ? 'the page never finished loading' : 'did not run'),
        };
      });

      resolve({
        runId: request.runId,
        output: (payload?.logs ?? []).join('\n'),
        error: timedOut ? `Gave up after ${TIMEOUT_MS / 1000}s.` : payload?.error ?? null,
        tests,
        durationMs: Date.now() - started,
      });
    };

    const onMessage = (event: MessageEvent) => {
      // A sandboxed frame's origin is the string "null", so it proves nothing.
      // The nonce is generated per run and never leaves this page except
      // inside the document we just wrote.
      const data = event.data as FramePayload | undefined;
      if (!data || data.nonce !== nonce) return;
      finish(data, false);
    };

    const timer = setTimeout(() => finish(null, true), TIMEOUT_MS);
    window.addEventListener('message', onMessage);
    frame.srcdoc = buildDocument(request, nonce);
  });
}
