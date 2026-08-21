/// <reference lib="webworker" />
/**
 * Runs a project's Python in a Web Worker, under Pyodide.
 *
 * The worker exists for one reason above all: a learner *will* write
 * `while True: pass`, and on the main thread that freezes the tab with no way
 * back. Here the UI simply terminates the worker and starts a new one.
 *
 * Each file becomes a real module registered in `sys.modules`, so a project can
 * ship `fixtures.py` alongside `solution.py` and the brief can say
 * `from fixtures import ROWS` — and so a test can do `import solution;
 * solution.sleep = spy` and have the patch be visible to code inside the
 * module, exactly as it would be under CPython.
 */

import type { RunRequest, RunResult, TestOutcome, WorkerMessage } from './runtime-protocol';

type Pyodide = {
  runPython: (code: string) => unknown;
  setStdout: (options: { batched: (text: string) => void }) => void;
  setStderr: (options: { batched: (text: string) => void }) => void;
  globals: { set: (name: string, value: unknown) => void };
};

declare const self: DedicatedWorkerGlobalScope;

type PyodideModule = {
  loadPyodide: (options: { indexURL: string }) => Promise<Pyodide>;
};

/**
 * Run `body` with `self.importScripts` hidden, restoring it whichever way the
 * call ends. See the note in `boot`.
 *
 * It has to be shadowed with an own property rather than deleted: the real
 * `importScripts` lives on `WorkerGlobalScope.prototype`, so `delete
 * self.importScripts` removes nothing and leaves the function perfectly
 * visible. Deleting the own property afterwards uncovers the inherited one
 * again.
 */
async function withoutImportScripts<T>(body: () => Promise<T>): Promise<T> {
  Object.defineProperty(self, 'importScripts', {
    value: undefined,
    configurable: true,
    writable: true,
  });
  try {
    return await body();
  } finally {
    delete (self as Partial<DedicatedWorkerGlobalScope>).importScripts;
  }
}

let pyodide: Pyodide | null = null;
let captured: string[] = [];

async function boot(): Promise<Pyodide> {
  if (pyodide) return pyodide;

  // Loaded from `public/` rather than bundled: the wasm and stdlib are ~13MB
  // and have no business in the app bundle. The magic comments stop the
  // bundler trying to resolve `/pyodide/…` — that is a URL served by `public/`
  // at runtime, not a module specifier it could ever find on disk.
  //
  // `importScripts` has to be out of sight while Pyodide's ESM entry is
  // evaluated. Pyodide 0.28+ (the `pyodide` 314.x line) probes for it at
  // module-evaluation time and throws "Classic web workers are not supported"
  // the moment it finds one — and Turbopack bootstraps *every* worker with a
  // classic stub that calls importScripts, whatever `type` the Worker was
  // constructed with. Nothing here needs importScripts, and it goes straight
  // back afterwards so the bundler's own lazy chunk loading still works.
  const module_ = await withoutImportScripts(
    () =>
      import(
        /* webpackIgnore: true */ /* turbopackIgnore: true */ '/pyodide/pyodide.mjs'
      ) as Promise<PyodideModule>,
  );

  pyodide = await module_.loadPyodide({ indexURL: '/pyodide/' });
  pyodide.setStdout({ batched: (text) => captured.push(text) });
  pyodide.setStderr({ batched: (text) => captured.push(text) });
  return pyodide;
}

/**
 * Python-side harness. Defined once, then called per run.
 *
 * `_load_files` installs each file as a module. `_run_test` copies the entry
 * module's namespace into fresh globals so tests cannot leak state into each
 * other, while still sharing the module objects themselves.
 */
const HARNESS = `
import sys, types, traceback

def _load_files(files, entry):
    for name in list(sys.modules):
        if getattr(sys.modules[name], "__skillatlas__", False):
            del sys.modules[name]

    modules = {}
    for path, source in files:
        if not path.endswith(".py"):
            continue
        name = path[:-3].replace("/", ".")
        module = types.ModuleType(name)
        module.__dict__["__name__"] = name
        module.__skillatlas__ = True
        sys.modules[name] = module
        modules[name] = (module, source, path)

    for name, (module, source, path) in modules.items():
        exec(compile(source, path, "exec"), module.__dict__)

    return sys.modules[entry[:-3].replace("/", ".")]

def _run_test(entry_module, code, name):
    """Return "" when the test passes, or the failure message.

    Deliberately a string rather than None: Python's None crosses the FFI as
    JavaScript's undefined, not null, so an === null check on the other side
    would score every passing test as a failure.
    """
    namespace = dict(entry_module.__dict__)
    try:
        exec(compile(code, name, "exec"), namespace)
        return ""
    except AssertionError as exc:
        return str(exc) or "assertion failed"
    except Exception:
        lines = traceback.format_exc().strip().splitlines()
        return lines[-1] if lines else "failed"
`;

async function run(request: RunRequest): Promise<RunResult> {
  const started = Date.now();
  captured = [];

  const py = await boot();
  py.runPython(HARNESS);

  const tests: TestOutcome[] = [];
  let error: string | null = null;

  py.globals.set(
    '_files',
    request.files.map((file) => [file.path, file.content]),
  );
  py.globals.set('_entry', request.entryPath);

  try {
    py.runPython('_entry_module = _load_files(_files, _entry)');
  } catch (exception) {
    // A syntax error or a module-level exception: nothing can be tested.
    error = String(exception).split('\n').slice(-8).join('\n').trim();
    return { runId: request.runId, output: captured.join(''), error, tests, durationMs: Date.now() - started };
  }

  for (const test of request.tests) {
    py.globals.set('_test_code', test.code);
    py.globals.set('_test_name', test.name);
    let message = '';
    try {
      message = (py.runPython('_run_test(_entry_module, _test_code, _test_name)') ??
        '') as string;
    } catch (exception) {
      // The harness itself blew up — treat it as a failure rather than losing
      // the whole run.
      message = String(exception).split('\n').slice(-1)[0] || 'failed';
    }
    tests.push({
      testId: test.id,
      name: test.name,
      passed: message === '',
      message: message || null,
    });
  }

  return {
    runId: request.runId,
    output: captured.join(''),
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

// Start downloading the runtime immediately rather than on the first Run.
boot().then(
  () => self.postMessage({ type: 'ready' } satisfies WorkerMessage),
  (exception: unknown) =>
    self.postMessage({
      type: 'fatal',
      message: `Could not start Python: ${
        exception instanceof Error ? exception.message : String(exception)
      }`,
    } satisfies WorkerMessage),
);
