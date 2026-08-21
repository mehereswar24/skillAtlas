/**
 * End-to-end check of /explore: sign up, browse a domain's routes, start one,
 * and confirm it lands on a real roadmap. Also covers search, the category
 * filter, and what a signed-out visitor gets.
 *
 * Needs both servers up:
 *   npx playwright install chromium      # once
 *   npm run check:explore
 */
import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:3000';
const email = `pw${Date.now()}@example.com`;
const results = [];
const check = (name, ok, detail = '') => {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`);
};

const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));

try {
  // Sign up through the BFF so the session cookie is set on this context.
  const signup = await page.request.post(`${BASE}/api/auth/signup`, {
    data: { email, password: 'Passw0rd!23' },
  });
  check('signup', signup.ok(), `HTTP ${signup.status()}`);

  await page.goto(`${BASE}/explore`, { waitUntil: 'networkidle', timeout: 120000 });
  check('explore loads', true, await page.title());

  const cards = page.getByRole('button', { name: /Browse routes/i });
  const cardCount = await cards.count();
  check('domain cards render', cardCount === 15, `${cardCount} cards`);

  // Compared against the API rather than hard-coded, so adding a track does not
  // fail this test — the point is that the header reflects real content.
  const [apiDomains, apiTracks] = await Promise.all([
    (await page.request.get(`${BASE}/api/domains`)).json(),
    (await page.request.get(`${BASE}/api/tracks`)).json(),
  ]);
  const apiConcepts = apiTracks.reduce((sum, t) => sum + t.concept_count, 0);
  const headerText = await page.locator('main').innerText();
  const expected = `${apiDomains.length} domains, ${apiTracks.length} routes, ${apiConcepts} concepts`;
  check(
    'header counts match the API',
    headerText.includes(expected),
    expected,
  );

  // Open Backend — the densest domain, 20 routes.
  await page.locator('button:has(h3:text-is("Backend"))').first().click();
  const dialog = page.getByRole('dialog');
  await dialog.waitFor({ state: 'visible', timeout: 15000 });
  check('route picker opens', true, (await dialog.locator('h2').innerText()));

  const routes = dialog.locator('ul > li');
  const routeCount = await routes.count();
  check('lists every route in the domain', routeCount === 20, `${routeCount} routes`);

  // Expand one route and start it.
  const first = routes.first();
  const routeName = await first.locator('button').first().innerText();
  await first.locator('button').first().click();
  await dialog.getByRole('button', { name: /Start this route/i }).waitFor({ timeout: 10000 });
  check('route expands with pace options', true, routeName.split('\n')[0]);

  await dialog.getByRole('button', { name: /^Focused/ }).click();
  await dialog.getByRole('button', { name: /Start this route/i }).click();

  await page.waitForURL('**/roadmap', { timeout: 180000 });
  check('starting a route navigates to /roadmap', true, page.url());

  const roadmapText = await page.locator('main').innerText();
  const hasWeeks = /Week\s*1/i.test(roadmapText);
  check('roadmap has a real weekly plan', hasWeeks, roadmapText.slice(0, 90).replace(/\n/g, ' | '));

  check('no uncaught page errors', errors.length === 0, errors.slice(0, 2).join(' ; '));

  // --- search and filter -------------------------------------------------
  await page.goto(`${BASE}/explore`, { waitUntil: 'networkidle', timeout: 120000 });
  const cardsFor = async () =>
    page.locator('button:has(h3)').filter({ hasText: /concepts/ }).count();

  await page.locator('input[type="search"]').fill('kubernetes');
  await page.waitForTimeout(400);
  const searched = await cardsFor();
  check('search narrows the domains', searched > 0 && searched < 15, `${searched} of 15`);

  await page.locator('input[type="search"]').fill('zzzznotathing');
  await page.waitForTimeout(400);
  const empty = await page.getByText(/Nothing matches/i).isVisible();
  check('empty search explains itself', empty);

  await page.locator('input[type="search"]').fill('');
  await page.waitForTimeout(400);
  await page.getByRole('button', { name: /All Categories/i }).click();
  // The vendored DropdownMenuItem renders a bare <div> with no role, so this
  // has to select on text rather than getByRole('menuitem').
  await page.locator('div').filter({ hasText: /^Design$/ }).last().click();
  await page.waitForTimeout(400);
  const designOnly = await cardsFor();
  check('category filter narrows the domains', designOnly > 0 && designOnly < 15,
    `${designOnly} in Design`);

  // --- signed out --------------------------------------------------------
  const anon = await browser.newContext();
  const anonPage = await anon.newPage();
  await anonPage.goto(`${BASE}/explore`, { waitUntil: 'networkidle', timeout: 120000 });
  check('explore is browsable signed out',
    (await anonPage.locator('button:has(h3:text-is("Design"))').count()) > 0);

  await anonPage.locator('button:has(h3:text-is("Design"))').first().click();
  const anonDialog = anonPage.getByRole('dialog');
  await anonDialog.waitFor({ state: 'visible', timeout: 15000 });
  await anonDialog.locator('ul > li').first().locator('button').first().click();
  await anonDialog.getByRole('button', { name: /Start this route/i }).click();
  await anonPage.waitForURL('**/login**', { timeout: 60000 });
  check('starting signed out goes to login', /\/login/.test(anonPage.url()), anonPage.url());
  await anon.close();
} catch (err) {
  check('run completed without throwing', false, String(err).slice(0, 200));
} finally {
  await browser.close();
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);
