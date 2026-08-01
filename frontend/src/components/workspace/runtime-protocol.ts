/**
 * The contract between the workspace UI and whichever runtime executes a
 * project — a Pyodide worker, a sql.js worker, or a sandboxed iframe.
 *
 * Keeping all three behind one message shape is what lets `code-workspace.tsx`
 * stay ignorant of which language it is running: it sends a RunRequest and
 * renders a RunResult.
 */

export type WorkspaceFile = {
  path: string;
  content: string;
};

export type RuntimeTest = {
  id: number;
  name: string;
  kind: 'python-assert' | 'dom-assert' | 'sql-result';
  code: string;
  expected: string | null;
  is_hidden: boolean;
};

export type RunRequest = {
  /** Echoed back on the result so a stale reply can be discarded. */
  runId: string;
  files: WorkspaceFile[];
  entryPath: string;
  /** Empty when the learner pressed Run rather than Run tests. */
  tests: RuntimeTest[];
};

export type TestOutcome = {
  testId: number;
  name: string;
  passed: boolean;
  /** The assertion message, or the diff for a SQL result. */
  message: string | null;
};

export type RunResult = {
  runId: string;
  /** Anything the program printed, in order. */
  output: string;
  /** Set when the program itself failed before any test could run. */
  error: string | null;
  tests: TestOutcome[];
  durationMs: number;
};

export type WorkerMessage =
  | { type: 'ready' }
  | { type: 'result'; result: RunResult }
  | { type: 'fatal'; message: string };

export const RUNTIME_LABELS: Record<string, string> = {
  python: 'Python',
  web: 'HTML, CSS & JavaScript',
  sql: 'SQL',
};

/** File extension → CodeMirror language, and the icon-free label we show. */
export function languageForPath(path: string): 'python' | 'javascript' | 'html' | 'css' | 'sql' | 'text' {
  if (path.endsWith('.py')) return 'python';
  if (path.endsWith('.js') || path.endsWith('.mjs')) return 'javascript';
  if (path.endsWith('.html')) return 'html';
  if (path.endsWith('.css')) return 'css';
  if (path.endsWith('.sql')) return 'sql';
  return 'text';
}
