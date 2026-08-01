/**
 * Run every `web` project's tests against its reference solution, in jsdom.
 *
 * The real runtime is a sandboxed iframe in a browser; jsdom is not that, and
 * the difference matters — it has no layout engine, so anything depending on
 * real geometry cannot be checked here. What it *does* catch is the whole
 * class of bug that actually bites when authoring these projects: a test that
 * references an element the starter never creates, an assertion with a typo in
 * a selector, or a reference solution that does not satisfy its own brief.
 *
 *     node scripts/check-web-projects.mjs
 *
 * Assertions that jsdom cannot judge are listed in SKIP below, with the reason.
 * They are reported as skipped rather than silently passed — a check that
 * quietly returns true when it cannot evaluate anything is worse than no check.
 */

import { readdir, readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { JSDOM, VirtualConsole } from 'jsdom';
import { parse } from 'yaml';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const PROJECTS = join(dirname(ROOT), 'backend', 'app', 'seed', 'projects');

/** test name → why jsdom cannot decide it. */
const SKIP = new Map([
  ['The grid actually uses CSS Grid', 'jsdom has no layout engine'],
  ['Cards use border-box sizing', 'jsdom does not cascade this shorthand'],
  ['A long word cannot overflow a card', 'jsdom does not cascade overflow-wrap'],
  ['It is fast', 'timing is meaningless without a layout engine'],
]);

const GREEN = '[32m';
const RED = '[31m';
const YELLOW = '[33m';
const RESET = '[0m';

async function loadWebProjects() {
  const projects = [];
  for (const file of (await readdir(PROJECTS)).filter((n) => n.endsWith('.yaml'))) {
    const data = parse(await readFile(join(PROJECTS, file), 'utf8'));
    for (const project of data.projects ?? []) {
      if (project.runtime === 'web') projects.push(project);
    }
  }
  return projects;
}

async function referenceFiles(project) {
  const files = new Map((project.files ?? []).map((f) => [f.path, f.content ?? '']));
  const root = join(PROJECTS, '_reference', project.slug);
  let names;
  try {
    names = await readdir(root);
  } catch {
    return null; // no reference solution yet
  }
  for (const name of names) {
    files.set(name, await readFile(join(root, name), 'utf8'));
  }
  return files;
}

/** Mirrors buildDocument() in web-runtime.ts. */
function buildDocument(project, files) {
  const entry = project.files.find((f) => f.entry)?.path;
  const html = files.get(entry) ?? '';
  const css = [...files]
    .filter(([path]) => path.endsWith('.css'))
    .map(([, content]) => content)
    .join('\n');
  const js = [...files]
    .filter(([path]) => path.endsWith('.js') && path !== entry)
    .map(([, content]) => content)
    .join('\n;\n');

  return `<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head>
<body>${html}<script>${js}<\/script></body></html>`;
}

let failures = 0;
let skipped = 0;
const projects = await loadWebProjects();

for (const project of projects) {
  const files = await referenceFiles(project);
  if (files === null) {
    console.log(`${YELLOW}SKIP${RESET} ${project.slug} — no reference solution`);
    skipped += 1;
    continue;
  }

  const virtualConsole = new VirtualConsole();
  const errors = [];
  virtualConsole.on('jsdomError', (error) => errors.push(error.message));

  const dom = new JSDOM(buildDocument(project, files), {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    virtualConsole,
  });

  if (errors.length) {
    failures += 1;
    console.log(`${RED}FAIL${RESET} ${project.slug} — script error: ${errors[0]}`);
    continue;
  }

  let projectFailures = 0;
  let projectSkips = 0;

  for (const test of project.tests ?? []) {
    if (SKIP.has(test.name)) {
      projectSkips += 1;
      continue;
    }
    try {
      const passed = dom.window.eval(`(${test.code})`);
      if (!passed) {
        projectFailures += 1;
        console.log(`${RED}FAIL${RESET} ${project.slug} :: ${test.name} — returned falsy`);
      }
    } catch (error) {
      projectFailures += 1;
      console.log(`${RED}FAIL${RESET} ${project.slug} :: ${test.name}\n     ${error.message}`);
    }
  }

  // The other half of "the project is sound": the starter must not already
  // pass, or the learner is handed points for opening the page.
  const starter = new Map(
    (project.files ?? []).map((f) => [f.path, f.content ?? '']),
  );
  const starterDom = new JSDOM(buildDocument(project, starter), {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    virtualConsole: new VirtualConsole(),
  });
  const starterPasses = (project.tests ?? [])
    .filter((test) => !SKIP.has(test.name))
    .every((test) => {
      try {
        return Boolean(starterDom.window.eval(`(${test.code})`));
      } catch {
        return false;
      }
    });
  if (starterPasses) {
    projectFailures += 1;
    console.log(
      `${RED}FAIL${RESET} ${project.slug} — the starter files already pass every test`,
    );
  }

  failures += projectFailures;
  skipped += projectSkips;
  if (!projectFailures) {
    const ran = (project.tests?.length ?? 0) - projectSkips;
    const note = projectSkips ? `, ${projectSkips} browser-only` : '';
    console.log(`${GREEN}ok${RESET}   ${project.slug} — ${ran} tests in jsdom${note}`);
  }
}

console.log();
if (skipped) {
  console.log(
    `${YELLOW}${skipped} assertion(s)/project(s) need a real browser:${RESET}`,
  );
  for (const [name, reason] of SKIP) console.log(`  - ${name}: ${reason}`);
}
if (failures) {
  console.error(`${RED}${failures} check(s) failed.${RESET}`);
  process.exit(1);
}
console.log(`${GREEN}Every web project's reference solution passes what jsdom can judge.${RESET}`);
