import { chromium } from 'playwright';
const BASE = 'http://127.0.0.1:3000';
const results = [];
const check = (n, ok, d = '') => { results.push({ n, ok, d }); console.log(`${ok ? 'PASS' : 'FAIL'}  ${n}${d ? ` — ${d}` : ''}`); };
const browser = await chromium.launch();
const ctx = await browser.newContext();
const page = await ctx.newPage();
page.setDefaultNavigationTimeout(180000);
page.setDefaultTimeout(60000);
const errors = [];
page.on('pageerror', e => errors.push('pageerror: ' + String(e)));
page.on('console', m => m.type() === 'error' && errors.push('console: ' + m.text()));

// Count API calls per navigation so N+1 patterns show up.
let apiCalls = [];
page.on('request', r => { const u = r.url(); if (u.includes('/api/')) apiCalls.push(`${r.method()} ${u.replace(BASE, '')}`); });

const timed = async (label, fn) => { const s = Date.now(); apiCalls = []; const r = await fn(); const ms = Date.now() - s; console.log(`   [t] ${label}: ${ms}ms, ${apiCalls.length} /api calls`); return r; };

const email = `jq${Date.now()}@example.com`;
const pw = 'Passw0rd!23';

try {
  // ---- sign up through the UI ----
  await page.goto(BASE + '/signup', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);
  await page.fill('#email', email);
  await page.fill('#password', pw);
  await page.getByRole('button', { name: /Create account/i }).click();
  await page.waitForURL(u => u.pathname === '/explore', { timeout: 180000 });
  check('signup -> explore', true, page.url());

  // ---- explore ----
  await timed('explore settle', () => page.waitForLoadState('networkidle'));

  // Search: nonsense query
  const searchInput = page.locator('input[type=search]');
  await searchInput.click();
  await searchInput.fill('zzzzzzz-nothing-matches');
  await page.waitForTimeout(400);
  check('nonsense search shows an empty state',
    await page.getByText(/Nothing matches/i).count() > 0);

  // Special characters must not crash the filter
  await searchInput.fill('<script>alert(1)</script>');
  await page.waitForTimeout(400);
  check('html in search does not execute or crash', await page.locator('main').count() === 1);
  await searchInput.fill('a'.repeat(3000));
  await page.waitForTimeout(400);
  check('3000-char search survives', await page.locator('main').count() === 1);
  await searchInput.fill('');
  await page.waitForTimeout(400);

  // Disabled domain cards (no routes) must not be clickable
  const disabled = page.locator('button:disabled:has(h3)');
  const disabledCount = await disabled.count();
  console.log(`   disabled domain cards: ${disabledCount}`);

  // ---- open a domain, start a route ----
  await page.locator('button:has(h3:text-is("Backend"))').first().click();
  const dialog = page.getByRole('dialog');
  await dialog.waitFor({ state: 'visible' });

  // Escape should close a modal dialog.
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);
  check('Escape closes the route picker', await dialog.count() === 0, `${await dialog.count()} dialogs still open`);
  if (await dialog.count() > 0) { await page.locator('button[aria-label=Close]').click(); }

  await page.locator('button:has(h3:text-is("Backend"))').first().click();
  await dialog.waitFor({ state: 'visible' });

  // focus trap check: after opening, is focus inside the dialog?
  const focusInDialog = await page.evaluate(() => {
    const d = document.querySelector('[role=dialog]');
    return d ? d.contains(document.activeElement) : null;
  });
  check('focus moves into the dialog', focusInDialog === true, String(focusInDialog));

  await dialog.locator('button:has-text("Backend Roadmap")').first().click();
  await page.waitForTimeout(400);

  // Double-click "Start this route" — should not create two roadmaps.
  const startBtn = dialog.getByRole('button', { name: /Start this route/i });
  let postCount = 0;
  const countPosts = r => { if (r.method() === 'POST' && r.url().includes('/api/roadmaps')) postCount++; };
  page.on('request', countPosts);
  const s = Date.now();
  await startBtn.click();
  await startBtn.click({ force: true, timeout: 1500 }).catch(() => { });
  await startBtn.click({ force: true, timeout: 1500 }).catch(() => { });
  await page.waitForURL(u => u.pathname === '/roadmap', { timeout: 180000 });
  console.log(`   [t] start route -> /roadmap: ${Date.now() - s}ms`);
  page.off('request', countPosts);
  check('double-click "Start this route" posts once', postCount === 1, `${postCount} POSTs`);

  await page.waitForLoadState('networkidle');
  const routesAfter = await (await page.request.get(BASE + '/api/roadmaps')).json();
  check('only one roadmap exists after triple-click', routesAfter.length === 1, `${routesAfter.length} roadmaps`);

  // ---- roadmap page ----
  const weekCount = await page.locator('ol > li').count();
  check('roadmap shows weeks', weekCount > 0, `${weekCount} weeks`);
  const pbar = page.locator('[aria-label="Route completion"]');
  check('progress bar present with aria', await pbar.count() === 1, await pbar.first().getAttribute('aria-valuenow'));

  // Locked items must not be links
  const lockedLinks = await page.locator('a[aria-disabled]').count();
  check('locked items are not links', lockedLinks === 0, `${lockedLinks}`);

  // ---- open a concept ----
  const firstConcept = page.locator('ol a[href^="/concepts/"]').first();
  const conceptHref = await firstConcept.getAttribute('href');
  await timed('roadmap -> concept', async () => { await firstConcept.click(); await page.waitForURL(u => u.pathname.startsWith('/concepts/'), { timeout: 180000 }); await page.waitForLoadState('networkidle'); });
  check('concept page opens', page.url().includes(conceptHref), page.url());
  console.log('   api calls on concept page: ' + JSON.stringify(apiCalls));

  // ---- back button ----
  await page.goBack({ waitUntil: 'domcontentloaded' });
  check('back returns to /roadmap', new URL(page.url()).pathname === '/roadmap', page.url());
  await page.goForward({ waitUntil: 'domcontentloaded' });
  check('forward returns to the concept', page.url().includes(conceptHref), page.url());

  // ---- refresh mid-flow ----
  await page.reload({ waitUntil: 'networkidle' });
  check('concept survives a refresh', page.url().includes(conceptHref) && await page.locator('h1').count() > 0, await page.locator('h1').first().innerText());

  // ---- complete the concept ----
  const quizCount = await page.locator('form, fieldset').count();
  const completeBtn = page.getByRole('button', { name: /complete|mark|finish|done/i });
  const nBtns = await completeBtn.count();
  console.log(`   complete-ish buttons: ${nBtns}`);
  if (nBtns > 0) {
    let completePosts = 0;
    const cp = r => { if (r.method() === 'POST' && r.url().includes('/complete')) completePosts++; };
    page.on('request', cp);
    const s2 = Date.now();
    await completeBtn.first().click();
    await completeBtn.first().click({ force: true, timeout: 1500 }).catch(() => { });
    await page.waitForTimeout(6000);
    console.log(`   [t] complete concept: ${Date.now() - s2}ms`);
    page.off('request', cp);
    check('double-click complete posts once', completePosts <= 1, `${completePosts} POSTs`);
    const progress = await (await page.request.get(BASE + '/api/progress')).json();
    const done = progress.filter(p => p.status === 'completed');
    check('completion recorded', done.length >= 1, `${done.length} completed`);
  } else {
    check('a complete control exists on the concept page', false, 'none found');
  }

  // ---- roadmap reflects completion ----
  await timed('roadmap after completion', async () => { await page.goto(BASE + '/roadmap', { waitUntil: 'networkidle' }); });
  const pct = await page.locator('[aria-label="Route completion"]').first().getAttribute('aria-valuenow');
  check('roadmap progress moved off zero', Number(pct) > 0, `${pct}%`);

  // ---- dashboard ----
  await timed('dashboard load', async () => { await page.goto(BASE + '/dashboard', { waitUntil: 'networkidle' }); });
  console.log('   dashboard api calls: ' + JSON.stringify(apiCalls));
  const dashText = await page.locator('main').innerText();
  check('dashboard shows the current track', /Bearing set for/i.test(dashText), dashText.split('\n').slice(0, 4).join(' | '));
  check('dashboard concept counter moved', !/^0\//m.test(dashText), (dashText.match(/Concepts covered\n(\S+)/) || [])[1]);

  // ---- deep link in a fresh tab (same session) ----
  const p2 = await ctx.newPage();
  p2.setDefaultNavigationTimeout(180000);
  await p2.goto(BASE + conceptHref, { waitUntil: 'domcontentloaded' });
  check('deep link in a fresh tab works', p2.url().includes(conceptHref), p2.url());
  await p2.goto(BASE + '/concepts/this-slug-does-not-exist', { waitUntil: 'domcontentloaded' });
  const notFound = await p2.locator('body').innerText();
  check('unknown concept slug 404s cleanly', /not found|404/i.test(notFound), notFound.slice(0, 120).replace(/\n/g, ' '));
  await p2.close();

  // ---- sign out ----
  await page.goto(BASE + '/dashboard', { waitUntil: 'networkidle' });
  const signOut = page.getByRole('button', { name: /sign out|log out/i });
  const soCount = await signOut.count();
  check('a sign-out control is reachable', soCount > 0, `${soCount} found`);
  if (soCount > 0) {
    await signOut.first().click();
    await page.waitForTimeout(4000);
    const cookies = await ctx.cookies();
    check('sign-out clears the session cookies', !cookies.some(c => c.name.startsWith('sa_')), JSON.stringify(cookies.map(c => c.name)));
    await page.goto(BASE + '/dashboard', { waitUntil: 'domcontentloaded' });
    check('after sign-out /dashboard bounces to login', new URL(page.url()).pathname === '/login', page.url());
  }

  check('no uncaught page errors', errors.length === 0, errors.slice(0, 6).join(' | '));
  console.log('\nCREDS ' + email + ' ' + pw + '  concept=' + conceptHref);
} catch (e) {
  check('harness completed', false, String(e).slice(0, 400));
} finally {
  await browser.close();
  const failed = results.filter(r => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  if (errors.length) console.log('ERRORS:\n' + [...new Set(errors)].slice(0, 20).join('\n'));
}
