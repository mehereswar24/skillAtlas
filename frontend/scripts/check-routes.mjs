/**
 * End-to-end check of running several routes at once: start three, switch
 * focus, rebuild one in place, and drop one.
 *
 * Needs both servers up:
 *   npx playwright install chromium      # once
 *   npm run check:routes
 */
import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:3000';
const email = `mr${Date.now()}@example.com`;
const results = [];
const check = (name, ok, detail = '') => {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`);
};

const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));

const startRoute = async (slug, pace = 'steady') =>
  page.request.post(`${BASE}/api/roadmaps`, { data: { track_slug: slug, pace } });

try {
  const signup = await page.request.post(`${BASE}/api/auth/signup`, {
    data: { email, password: 'Passw0rd!23' },
  });
  check('signup', signup.ok(), `HTTP ${signup.status()}`);

  for (const slug of ['backend', 'frontend', 'devops']) {
    const r = await startRoute(slug);
    if (!r.ok()) check(`start ${slug}`, false, `HTTP ${r.status()}`);
  }

  await page.goto(`${BASE}/roadmap`, { waitUntil: 'networkidle', timeout: 180000 });

  const cards = page.locator('section li:has([role="progressbar"])');
  check('switcher lists all three routes', (await cards.count()) === 3,
    `${await cards.count()} shown`);

  const focused = page.getByText('In focus');
  check('exactly one route is in focus', (await focused.count()) === 1);

  // Switch focus to a route that is not currently focused.
  const focusButtons = page.getByRole('button', { name: 'Focus' });
  check('unfocused routes offer a Focus button', (await focusButtons.count()) === 2);
  await focusButtons.first().click();
  await page.waitForTimeout(2500);
  await page.waitForLoadState('networkidle');
  check('still exactly one route in focus after switching',
    (await page.getByText('In focus').count()) === 1);

  const heading = await page.locator('h1').first().innerText();
  const focusedCard = await page
    .locator('section li:has-text("In focus")')
    .first()
    .innerText();
  check('the page follows the focused route',
    focusedCard.split('\n')[0].trim() === heading.trim(),
    `${heading} vs ${focusedCard.split('\n')[0]}`);

  // Rebuilding an existing route must not create a duplicate.
  const rebuilt = await startRoute('backend', 'intense');
  check('restarting a route succeeds', rebuilt.ok(), `HTTP ${rebuilt.status()}`);
  const list = await (await page.request.get(`${BASE}/api/roadmaps`)).json();
  check('restarting rebuilds in place, no duplicate', list.length === 3,
    `${list.length} routes`);
  const backend = list.find((r) => r.track.slug === 'backend');
  check('rebuild applied the new pace', backend?.pace === 'intense', backend?.pace);

  // Drop a route.
  await page.goto(`${BASE}/roadmap`, { waitUntil: 'networkidle', timeout: 180000 });
  await page.getByRole('button', { name: /Drop route/i }).first().click();
  await page.getByRole('button', { name: /^Drop$/ }).click();
  await page.waitForTimeout(2500);
  await page.waitForLoadState('networkidle');
  const after = await (await page.request.get(`${BASE}/api/roadmaps`)).json();
  check('dropping removes one route', after.length === 2, `${after.length} left`);
  check('a route is still focused after dropping',
    after.filter((r) => r.is_focused).length === 1);

  check('no uncaught page errors', errors.length === 0, errors.slice(0, 2).join(' ; '));
} catch (err) {
  check('run completed without throwing', false, String(err).slice(0, 220));
} finally {
  await browser.close();
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);
