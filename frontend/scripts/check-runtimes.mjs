/**
 * Confirms the in-browser project runtimes boot AND actually run tests.
 *
 * This exists because nothing else covers the real path. `verify_projects.py`
 * runs Python under CPython, and `check-web-projects.mjs` runs the web
 * projects under jsdom — so a broken Pyodide or sql.js Web Worker passes both
 * and still fails for every learner who opens a project. This drives a real
 * browser and clicks the button.
 *
 *   npm run check:runtimes        # needs both servers up
 */
import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:3000';
const results = [];
const check = (name, ok, detail = '') => {
  results.push({ name, ok });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`);
};

const TARGETS = [
  ['http-message-parser', 'python'],
  ['lru-cache-doubly-linked-list', 'python'],
  ['dedupe-keep-newest', 'sql'],
  ['debounce-and-throttle', 'web'],
];

const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => {
  if (m.type() === 'error') errors.push(m.text());
});

try {
  await page.request.post(`${BASE}/api/auth/signup`, {
    data: { email: `rt${Date.now()}@example.com`, password: 'Passw0rd!23' },
  });

  for (const [slug, runtime] of TARGETS) {
    errors.length = 0;
    await page.goto(`${BASE}/projects/${slug}`, {
      waitUntil: 'domcontentloaded',
      timeout: 180000,
    });

    const runBtn = page.getByRole('button', { name: /Run tests/i });
    await runBtn.waitFor({ timeout: 90000 });

    // The button is disabled until the runtime finishes booting.
    const booted = await page
      .waitForFunction(
        () => {
          const b = [...document.querySelectorAll('button')].find((x) =>
            /Run tests/i.test(x.textContent || ''),
          );
          return Boolean(b) && !b.disabled;
        },
        { timeout: 120000 },
      )
      .then(() => true)
      .catch(() => false);

    const workerError = errors.find((e) => /worker|importScripts|module/i.test(e));
    check(
      `${slug} (${runtime}) runtime boots`,
      booted,
      booted ? 'Run enabled' : (workerError ?? 'Run stayed disabled').slice(0, 140),
    );
    if (!booted) continue;

    await runBtn.click();

    let verdict = '';
    for (let i = 0; i < 120; i++) {
      verdict = await page.locator('main').innerText();
      if (/passing|failing|Runtime failed|No tests ran/i.test(verdict)) break;
      await page.waitForTimeout(1000);
    }

    // What counts as "the runtime works" needs care. Every project ships a
    // starter that raises `NotImplementedError("Start here")`, so a *correct*
    // run of an untouched project reports "Runtime failed" — the learner's
    // code raised, which is the whole point of a starter. That traceback is
    // proof Python executed. A genuinely broken runtime never gets that far
    // and fails in the worker instead.
    const executed =
      /passing/i.test(verdict) || /NotImplementedError|Traceback|Start here/i.test(verdict);
    const workerBroke = errors.some((e) =>
      /importScripts|Classic web workers|Failed to construct 'Worker'/i.test(e),
    );
    const line = (
      verdict
        .split('\n')
        .find((l) => /passing|failing|Runtime failed|NotImplementedError/i.test(l)) ?? ''
    ).trim();
    check(
      `${slug} (${runtime}) executes learner code`,
      executed && !workerBroke,
      workerBroke ? 'worker failed to construct' : line || 'no verdict reached',
    );
  }
} catch (err) {
  check('run completed without throwing', false, String(err).slice(0, 220));
} finally {
  await browser.close();
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);
