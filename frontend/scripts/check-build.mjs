/**
 * End-to-end check of the Build section: every seeded project is listed,
 * opens, and arrives with a starter file and runnable tests.
 *
 * Needs both servers up:
 *   npx playwright install chromium      # once
 *   npm run check:build
 */
import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:3000';
const email = `bu${Date.now()}@example.com`;
const results = [];
const check = (name, ok, detail = '') => {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`);
};

const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));

try {
  await page.request.post(`${BASE}/api/auth/signup`, {
    data: { email, password: 'Passw0rd!23' },
  });

  const projects = await (await page.request.get(`${BASE}/api/projects`)).json();
  check('every project is served', projects.length === 55, `${projects.length} projects`);

  const byRuntime = projects.reduce((acc, p) => {
    acc[p.runtime] = (acc[p.runtime] ?? 0) + 1;
    return acc;
  }, {});
  check('all three runtimes are represented',
    byRuntime.python > 0 && byRuntime.sql > 0 && byRuntime.web > 0,
    JSON.stringify(byRuntime));

  // Every project detail must arrive complete enough to actually attempt.
  const broken = [];
  let noStarter = 0;
  let noTests = 0;
  for (const summary of projects) {
    const res = await page.request.get(`${BASE}/api/projects/${summary.slug}`);
    if (!res.ok()) {
      broken.push(`${summary.slug} HTTP ${res.status()}`);
      continue;
    }
    const p = await res.json();
    // The API serialises this as `is_entry`; `entry` is the YAML spelling.
    if (!(p.files ?? []).some((f) => f.is_entry)) noStarter += 1;
    if ((p.tests ?? []).length === 0) noTests += 1;
  }
  check('every project detail responds', broken.length === 0,
    broken.slice(0, 3).join('; ') || `${projects.length} walked`);
  check('every project ships an entry file', noStarter === 0, `${noStarter} missing`);
  check('every project ships tests', noTests === 0, `${noTests} missing`);

  // The new project sets must be reachable from their concepts.
  for (const slug of ['lru-cache-doubly-linked-list', 'dedupe-keep-newest', 'debounce-and-throttle']) {
    const res = await page.request.get(`${BASE}/api/projects/${slug}`);
    check(`${slug} is seeded`, res.ok(), `HTTP ${res.status()}`);
  }

  // Render checks.
  await page.goto(`${BASE}/projects`, { waitUntil: 'networkidle', timeout: 180000 });
  const links = await page.locator('a[href^="/projects/"]').count();
  check('build page lists projects', links >= 55, `${links} links`);

  await page.goto(`${BASE}/projects/lru-cache-doubly-linked-list`, {
    waitUntil: 'networkidle',
    timeout: 180000,
  });
  const text = await page.locator('main').innerText();
  check('a DSA project page renders its brief', text.length > 800 && !/not found/i.test(text),
    `${text.length} chars`);
  check('the workspace editor is present',
    (await page.locator('.cm-editor, textarea').count()) > 0);

  check('no uncaught page errors', errors.length === 0, errors.slice(0, 2).join(' ; '));
} catch (err) {
  check('run completed without throwing', false, String(err).slice(0, 220));
} finally {
  await browser.close();
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);
