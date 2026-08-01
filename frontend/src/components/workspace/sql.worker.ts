/// <reference lib="webworker" />
/**
 * Runs SQL projects against an in-memory SQLite built by sql.js.
 *
 * Every test gets a *fresh* database seeded from the project's schema file, so
 * a query with a side effect cannot make the next test pass. `{{query}}` in a
 * test is replaced by the learner's query, which is what lets a test wrap it
 * (`SELECT COUNT(*) FROM ({{query}}) WHERE ...`) and check one property rather
 * than the whole result set.
 */

import type { RunRequest, RunResult, TestOutcome, WorkerMessage } from './runtime-protocol';

declare const self: DedicatedWorkerGlobalScope;

type SqlDatabase = {
  run: (sql: string) => void;
  exec: (sql: string) => { columns: string[]; values: unknown[][] }[];
  close: () => void;
};

type SqlJs = { Database: new () => SqlDatabase };

let sqlJs: SqlJs | null = null;

async function boot(): Promise<SqlJs> {
  if (sqlJs) return sqlJs;
  // sql-wasm.js is a UMD script; importScripts is the way into a worker.
  self.importScripts('/sqljs/sql-wasm.js');
  const initSqlJs = (self as unknown as { initSqlJs: (config: object) => Promise<SqlJs> }).initSqlJs;
  sqlJs = await initSqlJs({ locateFile: () => '/sqljs/sql-wasm.wasm' });
  return sqlJs;
}

/** The schema file is whichever read-only .sql file creates tables. */
function schemaOf(request: RunRequest): string {
  const schema = request.files.find(
    (file) =>
      file.path !== request.entryPath &&
      file.path.endsWith('.sql') &&
      /create\s+table/i.test(file.content),
  );
  return schema?.content ?? '';
}

function normalise(rows: unknown[][]): unknown[][] {
  // sql.js returns numbers for INTEGER and REAL alike; JSON expectations are
  // written the same way, so a plain deep compare after this is enough.
  return rows.map((row) => row.map((cell) => (cell === undefined ? null : cell)));
}

function runQuery(db: SqlDatabase, sql: string): unknown[][] {
  const results = db.exec(sql);
  if (!results.length) return [];
  return normalise(results[results.length - 1].values);
}

async function run(request: RunRequest): Promise<RunResult> {
  const started = Date.now();
  const SQL = await boot();
  const schema = schemaOf(request);
  const query = (request.files.find((f) => f.path === request.entryPath)?.content ?? '')
    .trim()
    .replace(/;\s*$/, '');

  const output: string[] = [];
  const tests: TestOutcome[] = [];
  let error: string | null = null;

  // A bare Run shows the learner their own result set.
  if (!request.tests.length) {
    const db = new SQL.Database();
    try {
      db.run(schema);
      const rows = runQuery(db, query);
      output.push(
        rows.length
          ? rows.map((row) => row.join(' | ')).join('\n')
          : '(no rows)',
      );
    } catch (exception) {
      error = exception instanceof Error ? exception.message : String(exception);
    } finally {
      db.close();
    }
    return { runId: request.runId, output: output.join('\n'), error, tests, durationMs: Date.now() - started };
  }

  for (const test of request.tests) {
    const db = new SQL.Database();
    try {
      db.run(schema);
      const sql = test.code.replaceAll('{{query}}', query);
      const rows = runQuery(db, sql);
      const expected = JSON.parse(test.expected ?? '[]');

      const passed = JSON.stringify(rows) === JSON.stringify(expected);
      tests.push({
        testId: test.id,
        name: test.name,
        passed,
        message: passed
          ? null
          : `got ${JSON.stringify(rows)}\nexpected ${JSON.stringify(expected)}`,
      });
    } catch (exception) {
      tests.push({
        testId: test.id,
        name: test.name,
        passed: false,
        message: exception instanceof Error ? exception.message : String(exception),
      });
    } finally {
      db.close();
    }
  }

  return {
    runId: request.runId,
    output: output.join('\n'),
    error,
    tests,
    durationMs: Date.now() - started,
  };
}

self.addEventListener('message', async (event: MessageEvent<RunRequest>) => {
  try {
    const result = await run(event.data);
    self.postMessage({ type: 'result', result } satisfies WorkerMessage);
  } catch (exception) {
    self.postMessage({
      type: 'fatal',
      message: exception instanceof Error ? exception.message : String(exception),
    } satisfies WorkerMessage);
  }
});

boot().then(
  () => self.postMessage({ type: 'ready' } satisfies WorkerMessage),
  (exception: unknown) =>
    self.postMessage({
      type: 'fatal',
      message: `Could not start SQLite: ${
        exception instanceof Error ? exception.message : String(exception)
      }`,
    } satisfies WorkerMessage),
);
