/**
 * End-to-end check of the Companies section and the DSA track: every seeded
 * company opens, its roles open, and each role page shows sourced questions
 * and focus areas. Also confirms the DSA route is startable from Explore.
 *
 * Needs both servers up:
 *   npx playwright install chromium      # once
 *   npm run check:companies
 */
import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:3000';
const email = `co${Date.now()}@example.com`;
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

  const companies = await (await page.request.get(`${BASE}/api/companies`)).json();
  check('every company is served', companies.length === 30, `${companies.length} companies`);

  // Walk every company + role through the API, then render a sample in the UI.
  let roles = 0;
  let questions = 0;
  let unsourced = 0;
  const broken = [];

  for (const company of companies) {
    const detail = await page.request.get(`${BASE}/api/companies/${company.slug}`);
    if (!detail.ok()) {
      broken.push(`${company.slug} detail HTTP ${detail.status()}`);
      continue;
    }
    const body = await detail.json();
    for (const role of body.roles ?? []) {
      const roleRes = await page.request.get(
        `${BASE}/api/companies/${company.slug}/roles/${role.slug}`,
      );
      if (!roleRes.ok()) {
        broken.push(`${company.slug}/${role.slug} HTTP ${roleRes.status()}`);
        continue;
      }
      const roleBody = await roleRes.json();
      roles += 1;
      const qs = roleBody.questions ?? [];
      questions += qs.length;
      unsourced += qs.filter((q) => !q.source_url).length;
    }
  }

  check('every company and role endpoint responds', broken.length === 0,
    broken.slice(0, 3).join('; ') || `${roles} roles walked`);
  check('roles carry questions', questions > 300, `${questions} questions across ${roles} roles`);
  check('every question is source-cited', unsourced === 0, `${unsourced} unsourced`);

  // Render checks — the API being right does not mean the page shows it.
  await page.goto(`${BASE}/companies`, { waitUntil: 'networkidle', timeout: 120000 });
  const listed = await page.locator('a[href^="/companies/"]').count();
  check('companies page lists them', listed >= 30, `${listed} links`);

  for (const slug of ['flipkart', 'palantir', 'wipro']) {
    await page.goto(`${BASE}/companies/${slug}`, { waitUntil: 'networkidle', timeout: 120000 });
    const text = await page.locator('main').innerText();
    check(`${slug} profile renders`, text.length > 600 && !/not found/i.test(text),
      `${text.length} chars`);
  }

  // One role page, in full.
  await page.goto(`${BASE}/companies/flipkart`, { waitUntil: 'networkidle', timeout: 120000 });
  const roleLink = page.locator('a[href^="/companies/flipkart/"]').first();
  const roleHref = await roleLink.getAttribute('href');
  await roleLink.click();
  await page.waitForURL(`**${roleHref}`, { timeout: 60000 });
  const roleText = await page.locator('main').innerText();
  check('role page shows interview questions', /\?/.test(roleText) && roleText.length > 1200,
    `${roleText.length} chars`);
  const sourceLinks = await page.locator('main a[href^="https://"]').count();
  check('role page links its sources', sourceLinks > 0, `${sourceLinks} outbound links`);

  // The DSA track must be reachable and startable.
  const tracks = await (await page.request.get(`${BASE}/api/tracks`)).json();
  const dsa = tracks.find((t) => t.slug === 'dsa-interview-prep');
  check('DSA track is served', Boolean(dsa),
    dsa ? `${dsa.concept_count} concepts, ${dsa.total_hours}h` : 'missing');

  const started = await page.request.post(`${BASE}/api/roadmaps`, {
    data: { track_slug: 'dsa-interview-prep', pace: 'steady' },
  });
  check('DSA route can be started', started.ok(), `HTTP ${started.status()}`);

  await page.goto(`${BASE}/roadmap`, { waitUntil: 'networkidle', timeout: 180000 });
  const plan = await page.locator('main').innerText();
  check('DSA route renders a weekly plan', /Week\s*1/i.test(plan),
    plan.slice(0, 80).replace(/\n/g, ' | '));

  check('no uncaught page errors', errors.length === 0, errors.slice(0, 2).join(' ; '));
} catch (err) {
  check('run completed without throwing', false, String(err).slice(0, 220));
} finally {
  await browser.close();
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);
