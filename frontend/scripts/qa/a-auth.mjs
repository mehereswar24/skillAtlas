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

const t = async (label, fn) => { const s = Date.now(); const r = await fn(); console.log(`   [t] ${label}: ${Date.now() - s}ms`); return r; };

try {
  // ---------- landing ----------
  await t('landing goto', () => page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 120000 }));
  check('landing loads', (await page.title()).includes('SkillAtlas'), await page.title());

  // ---------- signed-out guards ----------
  for (const path of ['/dashboard', '/roadmap', '/concepts/http', '/projects']) {
    await page.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 120000 });
    const u = new URL(page.url());
    check(`signed-out ${path} -> login`, u.pathname === '/login' && u.searchParams.get('next') === path, page.url());
  }

  // ---------- signup form validation ----------
  await page.goto(BASE + '/signup', { waitUntil: 'domcontentloaded' });
  const submit = page.getByRole('button', { name: /Create account/i });
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);

  await submit.click();
  await page.waitForTimeout(500);
  check('signup empty submit stays put', new URL(page.url()).pathname === '/signup', page.url() + ' alerts=' + await page.locator('[role=alert]').count());

  await page.fill('#email', '   ');
  await page.fill('#password', 'abc');
  await submit.click();
  await page.waitForTimeout(600);
  let alert = await page.locator('[role=alert]').first().textContent().catch(() => null);
  check('signup short password blocked client-side', /8 characters/i.test(alert || ''), JSON.stringify(alert));

  await page.fill('#email', '   ');
  await page.fill('#password', 'Passw0rd!23');
  await submit.click();
  await page.waitForTimeout(2000);
  alert = await page.locator('[role=alert]').first().textContent().catch(() => null);
  check('signup whitespace email rejected with message', new URL(page.url()).pathname === '/signup' && !!alert, JSON.stringify(alert));

  await page.fill('#email', 'notanemail');
  await submit.click();
  await page.waitForTimeout(2000);
  alert = await page.locator('[role=alert]').first().textContent().catch(() => null);
  check('signup malformed email rejected with message', !!alert, JSON.stringify(alert));

  const long = 'a'.repeat(5000);
  await page.fill('#display_name', long);
  await page.fill('#email', long + '@example.com');
  await page.fill('#password', long);
  await submit.click();
  await page.waitForTimeout(4000);
  alert = await page.locator('[role=alert]').first().textContent().catch(() => null);
  check('signup absurdly long values rejected with message', new URL(page.url()).pathname === '/signup' && !!alert, JSON.stringify((alert || '').slice(0, 200)));

  // ---------- real signup ----------
  const email = `qa${Date.now()}@example.com`;
  const pw = 'Passw0rd!23';
  await page.fill('#display_name', 'QA Bot');
  await page.fill('#email', email);
  await page.fill('#password', pw);
  const s = Date.now();
  await submit.click();
  await page.waitForURL(u => !u.pathname.startsWith('/signup'), { timeout: 180000 });
  console.log(`   [t] signup->next page nav: ${Date.now() - s}ms`);
  check('signup lands on /explore', new URL(page.url()).pathname === '/explore', page.url());

  // ---------- signed-in on auth pages ----------
  await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
  check('signed-in /login redirects', new URL(page.url()).pathname === '/dashboard', page.url());
  await page.goto(BASE + '/signup', { waitUntil: 'domcontentloaded' });
  check('signed-in /signup redirects', new URL(page.url()).pathname === '/dashboard', page.url());
  await page.goto(BASE + '/login?next=%2Froadmap', { waitUntil: 'domcontentloaded' });
  check('signed-in /login?next honours next', new URL(page.url()).pathname === '/roadmap', page.url());

  // ---------- duplicate email ----------
  const ctx2 = await browser.newContext();
  const p2 = await ctx2.newPage();
  p2.setDefaultNavigationTimeout(180000); p2.setDefaultTimeout(60000);
  await p2.goto(BASE + '/signup', { waitUntil: 'domcontentloaded' });
  await p2.fill('#email', email);
  await p2.fill('#password', pw);
  await p2.getByRole('button', { name: /Create account/i }).click();
  await p2.waitForTimeout(3000);
  const dupAlert = await p2.locator('[role=alert]').first().textContent().catch(() => null);
  check('duplicate email shows a clear message', /already exists/i.test(dupAlert || ''), JSON.stringify(dupAlert));

  // ---------- wrong password ----------
  await p2.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
  await p2.fill('#email', email);
  await p2.fill('#password', 'wrongpassword123');
  await p2.getByRole('button', { name: /Sign in/i }).click();
  await p2.waitForTimeout(3000);
  const wrongAlert = await p2.locator('[role=alert]').first().textContent().catch(() => null);
  check('wrong password shows a clear message', /incorrect/i.test(wrongAlert || ''), JSON.stringify(wrongAlert));

  // ---------- login with next ----------
  await p2.goto(BASE + '/login?next=%2Froadmap', { waitUntil: 'domcontentloaded' });
  await p2.fill('#email', email);
  await p2.fill('#password', pw);
  await p2.getByRole('button', { name: /Sign in/i }).click();
  await p2.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 180000 }).catch(() => { });
  check('login honours ?next', new URL(p2.url()).pathname === '/roadmap', p2.url());

  // ---------- double-click submit ----------
  const ctx3 = await browser.newContext();
  const p3 = await ctx3.newPage();
  p3.setDefaultNavigationTimeout(180000); p3.setDefaultTimeout(60000);
  const reqs = [];
  p3.on('request', r => r.url().includes('/api/auth/login') && reqs.push(r.url()));
  await p3.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
  await p3.fill('#email', email);
  await p3.fill('#password', pw);
  const btn = p3.getByRole('button', { name: /Sign in/i });
  await btn.click();
  await btn.click({ force: true, timeout: 2000 }).catch(() => { });
  await btn.click({ force: true, timeout: 2000 }).catch(() => { });
  await p3.waitForTimeout(4000);
  check('double-click login fires one request', reqs.length === 1, `${reqs.length} requests`);

  // ---------- stale / tampered cookie (session expiry) ----------
  const ctx4 = await browser.newContext();
  await ctx4.addCookies([
    { name: 'sa_access', value: 'garbage.garbage.garbage', domain: '127.0.0.1', path: '/' },
    { name: 'sa_refresh', value: 'garbage.garbage.garbage', domain: '127.0.0.1', path: '/' },
  ]);
  const p4 = await ctx4.newPage();
  p4.setDefaultNavigationTimeout(180000); p4.setDefaultTimeout(60000);
  const nav4 = [];
  p4.on('framenavigated', f => f === p4.mainFrame() && nav4.push(f.url()));
  const s4 = Date.now();
  await p4.goto(BASE + '/dashboard', { waitUntil: 'domcontentloaded', timeout: 180000 }).catch(e => errors.push('expiry nav: ' + e.message));
  console.log(`   [t] expired-cookie /dashboard: ${Date.now() - s4}ms, ${nav4.length} navigations`);
  check('expired cookie -> /login (no loop)', new URL(p4.url()).pathname === '/login', p4.url() + ` navs=${nav4.length}`);
  const c4 = await ctx4.cookies();
  check('expired cookie cleared', !c4.some(c => c.name === 'sa_access' && c.value), JSON.stringify(c4.map(c => c.name + '=' + c.value.slice(0, 8))));

  // ---------- expired-cookie on a deep concept link ----------
  const ctx5 = await browser.newContext();
  await ctx5.addCookies([{ name: 'sa_refresh', value: 'garbage', domain: '127.0.0.1', path: '/' }]);
  const p5 = await ctx5.newPage();
  p5.setDefaultNavigationTimeout(180000); p5.setDefaultTimeout(60000);
  await p5.goto(BASE + '/concepts/http', { waitUntil: 'domcontentloaded', timeout: 180000 }).catch(e => errors.push('deep expiry: ' + e.message));
  check('expired cookie deep link -> login keeps next', new URL(p5.url()).pathname === '/login' && new URL(p5.url()).searchParams.get('next') === '/concepts/http', p5.url());

  check('no uncaught page errors', errors.length === 0, errors.slice(0, 5).join(' | '));
  console.log('\nCREDS ' + email + ' ' + pw);
} catch (e) {
  check('harness completed', false, String(e));
} finally {
  await browser.close();
  const failed = results.filter(r => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  if (errors.length) console.log('ERRORS:\n' + errors.slice(0, 15).join('\n'));
}
