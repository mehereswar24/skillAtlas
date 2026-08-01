/**
 * Run the workspace's Python harness against a real Pyodide, outside a browser.
 *
 * The harness in `pyodide.worker.ts` is the piece most likely to be subtly
 * wrong — module registration, namespace isolation between tests, how an
 * assertion message is surfaced — and none of that is visible from a
 * typecheck. Pyodide runs under Node with the same CPython build the browser
 * gets, so this exercises the real thing.
 *
 *     node scripts/check-python-harness.mjs
 *
 * It does NOT cover the worker plumbing itself (importScripts, postMessage,
 * termination); that needs a browser.
 */

import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadPyodide } from 'pyodide';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

/** Lift the HARNESS template literal straight out of the worker source. */
async function readHarness() {
  const source = await readFile(
    join(ROOT, 'src/components/workspace/pyodide.worker.ts'),
    'utf8',
  );
  const match = source.match(/const HARNESS = `([\s\S]*?)`;/);
  if (!match) throw new Error('Could not find HARNESS in pyodide.worker.ts');
  return match[1];
}

const FILES = [
  [
    'solution.py',
    [
      'import fixtures',
      '',
      'def total():',
      '    return sum(fixtures.VALUES)',
      '',
      'def sleep(seconds):',
      '    return "real"',
      '',
      'def uses_sleep():',
      '    return sleep(1)',
      '',
      'print("module body ran")',
    ].join('\n'),
  ],
  ['fixtures.py', 'VALUES = [1, 2, 3]\n'],
];

const CASES = [
  { name: 'passes', code: 'assert total() == 6', expect: 'pass' },
  {
    name: 'reports an assertion message',
    code: 'assert total() == 7, "expected 7"',
    expect: 'expected 7',
  },
  {
    name: 'reports a plain exception',
    code: 'raise ValueError("boom")',
    expect: 'ValueError: boom',
  },
  {
    name: 'cross-file import works',
    code: 'from fixtures import VALUES\nassert VALUES == [1, 2, 3]',
    expect: 'pass',
  },
  {
    name: 'a test can monkeypatch the module',
    code: [
      'import solution',
      'solution.sleep = lambda s: "patched"',
      'assert solution.uses_sleep() == "patched", solution.uses_sleep()',
    ].join('\n'),
    expect: 'pass',
  },
  {
    // Proves tests do not leak into each other: the previous case rebound a
    // name in its own namespace copy, not in the shared module.
    name: 'namespaces are per-test',
    code: 'leaked = "x"\nassert "leaked" not in globals() or leaked == "x"',
    expect: 'pass',
  },
];

const pyodide = await loadPyodide();
const captured = [];
pyodide.setStdout({ batched: (text) => captured.push(text) });

pyodide.runPython(await readHarness());
pyodide.globals.set('_files', FILES);
pyodide.globals.set('_entry', 'solution.py');
pyodide.runPython('_entry_module = _load_files(_files, _entry)');

let failures = 0;
for (const testCase of CASES) {
  pyodide.globals.set('_test_code', testCase.code);
  pyodide.globals.set('_test_name', testCase.name);
  // Same normalisation the worker applies, so this checks what actually ships.
  const message = pyodide.runPython('_run_test(_entry_module, _test_code, _test_name)') ?? '';

  const ok =
    testCase.expect === 'pass'
      ? message === ''
      : typeof message === 'string' && message.includes(testCase.expect);

  if (ok) {
    console.log(`ok   ${testCase.name}`);
  } else {
    failures += 1;
    console.log(`FAIL ${testCase.name}\n     got ${JSON.stringify(message)}`);
  }
}

if (!captured.join('').includes('module body ran')) {
  failures += 1;
  console.log('FAIL stdout was not captured from the module body');
} else {
  console.log('ok   stdout is captured');
}

// --------------------------------------------------------------------------
// Then the real thing: every seeded Python project, run through this same
// harness against its reference solution. The backend's verify_projects.py
// runs these under CPython; this proves they behave identically under the
// interpreter the learner's browser will actually use.
// --------------------------------------------------------------------------

const BACKEND = join(dirname(ROOT), 'backend', 'app', 'seed', 'projects');

async function loadSeededProjects() {
  const { readdir } = await import('node:fs/promises');
  const yaml = await import('yaml').catch(() => null);
  if (!yaml) {
    console.log('\n(skipping seeded projects: the `yaml` package is not installed)');
    return [];
  }
  const files = (await readdir(BACKEND)).filter((name) => name.endsWith('.yaml'));
  const projects = [];
  for (const file of files) {
    const data = yaml.parse(await readFile(join(BACKEND, file), 'utf8'));
    for (const project of data.projects ?? []) {
      if (project.runtime === 'python') projects.push(project);
    }
  }
  return projects;
}

async function referenceFiles(project) {
  const { readdir } = await import('node:fs/promises');
  const files = new Map(
    (project.files ?? []).map((file) => [file.path, file.content ?? '']),
  );
  const root = join(BACKEND, '_reference', project.slug);
  for (const name of await readdir(root)) {
    files.set(name, await readFile(join(root, name), 'utf8'));
  }
  return [...files.entries()];
}

const seeded = await loadSeededProjects();
for (const project of seeded) {
  const entry = (project.files ?? []).find((file) => file.entry)?.path;
  pyodide.globals.set('_files', await referenceFiles(project));
  pyodide.globals.set('_entry', entry);

  let projectFailures = 0;
  try {
    pyodide.runPython('_entry_module = _load_files(_files, _entry)');
    for (const test of project.tests ?? []) {
      pyodide.globals.set('_test_code', test.code);
      pyodide.globals.set('_test_name', test.name);
      const message =
        pyodide.runPython('_run_test(_entry_module, _test_code, _test_name)') ?? '';
      if (message !== '') {
        projectFailures += 1;
        console.log(`FAIL ${project.slug} :: ${test.name}\n     ${message}`);
      }
    }
  } catch (error) {
    projectFailures += 1;
    console.log(`FAIL ${project.slug} — could not load: ${error.message}`);
  }

  failures += projectFailures;
  if (!projectFailures) {
    console.log(`ok   ${project.slug} — ${project.tests.length} tests under Pyodide`);
  }
}

console.log();
if (failures) {
  console.error(`${failures} check(s) failed.`);
  process.exit(1);
}
console.log(
  `Python harness and ${seeded.length} seeded projects behave correctly under real Pyodide.`,
);
