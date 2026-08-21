/**
 * Drives EVERY project end to end in a real browser:
 * boot -> restore the reference solution -> Run tests -> Submit -> XP.
 */
import { chromium } from 'playwright';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const BASE = 'http://127.0.0.1:3000';
const API  = 'http://127.0.0.1:8011';
const REF  = 'C:/Users/Mehereswar/Desktop/skillatlas/backend/app/seed/projects/_reference';
const only = process.argv[2] ? process.argv[2].split(',') : null;
const RECYCLE = 4;   // fresh browser every N projects — 55 Pyodide boots in one exhausts it

const all = await (await fetch(`${API}/api/v1/projects`)).json();
const targets = all.filter(p => !only || only.includes(p.slug) || only.includes(p.runtime));

let browser, ctx, page, done = 0;
const rows = [];

async function fresh() {
  if (browser) await browser.close();
  browser = await chromium.launch();
  ctx = await browser.newContext();
  page = await ctx.newPage();
  const r = await page.request.post(`${BASE}/api/auth/signup`,
    { data: { email: `qa${Date.now()}${Math.random().toString(36).slice(2,6)}@example.com`, password: 'Passw0rd!23' } });
  if (r.status() !== 201) throw new Error('signup ' + r.status());
}
await fresh();

for (const p of targets) {
  if (done && done % RECYCLE === 0) await fresh();
  done++;
  const slug = p.slug;
  const dir = join(REF, slug);
  const ref = {};
  if (existsSync(dir)) for (const f of readdirSync(dir)) ref[f] = readFileSync(join(dir, f), 'utf8');
  const row = { slug, rt: p.runtime, status: 'FAIL', note: '' };
  rows.push(row);

  try {
    await page.goto(`${BASE}/projects/${slug}`, { waitUntil: 'domcontentloaded', timeout: 240000 });
    await page.evaluate(([s, d]) => localStorage.setItem(`skillatlas-draft:${s}`, JSON.stringify(d)), [slug, ref]);
    const t0 = Date.now();
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 240000 });

    // CodeMirror is client-only, so its presence proves React has hydrated
    // and the draft-restore effect has run.
    await page.locator('.cm-content').first().waitFor({ timeout: 120000 });
    const tHydrate = Date.now();

    // Prove the reference solution is really in the editor before running it.
    const first = Object.keys(ref)[0];
    if (first) {
      await page.getByRole('button', { name: new RegExp(`^${first.replace('.', '\.')}`) }).click().catch(() => {});
      const inEditor = await page.locator('.cm-content').first().innerText();
      const want = ref[first].split('\n').find(l => l.trim().length > 12) ?? '';
      if (want && !inEditor.replace(/\s+/g, ' ').includes(want.trim().replace(/\s+/g, ' ').slice(0, 40))) {
        row.note = 'reference solution did not reach the editor'; console.log(`FAIL ${p.runtime} ${slug} — ${row.note}`); continue;
      }
    }

    const booted = await page.waitForFunction(
      () => { const b = [...document.querySelectorAll('button')].find(x => /^\s*Run tests\s*$/i.test(x.textContent || '')); return !!b && !b.disabled; },
      { timeout: 240000 }).then(() => true).catch(() => false);
    const tBoot = Date.now();
    if (!booted) {
      row.note = (await page.locator('[role=alert]').first().innerText().catch(() => '')) || 'Run tests stayed disabled';
      console.log(`FAIL ${p.runtime} ${slug} — boot: ${row.note.slice(0,90)}`); continue;
    }

    await page.getByRole('button', { name: /^Run tests$/ }).click();
    let verdict = '';
    for (let i = 0; i < 240; i++) {
      const m = (await page.locator('main').innerText()).match(/(\d+) \/ (\d+) passing/);
      if (m) { verdict = m[0]; break; }
      await page.waitForTimeout(500);
    }
    const tRun = Date.now();
    row.verdict = verdict; row.bootMs = tBoot - tHydrate; row.hydrateMs = tHydrate - t0; row.runMs = tRun - tBoot;
    if (!/^(\d+) \/ \1 passing$/.test(verdict) || /^0 \/ 0/.test(verdict)) {
      row.note = 'not all green';
      const fails = (await page.locator('main').innerText()).split('\n').slice(0, 60).filter(l => l.trim()).slice(-8).join(' | ');
      console.log(`FAIL ${p.runtime} ${slug} — ${verdict || 'no verdict'} :: ${fails.slice(0,160)}`); continue;
    }

    await page.getByRole('button', { name: /^Submit$/ }).click();
    await page.waitForFunction(() => /Shipped|tests passing|Could not/.test(document.body.innerText), { timeout: 60000 }).catch(() => {});
    const after = await page.locator('main').innerText();
    row.submit = (after.split('\n').map(s => s.trim()).find(l => /^(Shipped|\d+ of \d+ tests|Could not)/.test(l)) || '(none)');
    row.status = /^Shipped — \d+ points$/.test(row.submit) ? 'PASS' : 'FAIL';
    console.log(`${row.status} ${p.runtime.padEnd(6)} ${slug.padEnd(42)} ${verdict.padEnd(14)} ${row.submit.padEnd(26)} hydrate=${row.hydrateMs}ms boot=${row.bootMs}ms run=${row.runMs}ms`);
  } catch (e) {
    row.note = String(e).split('\n')[0].slice(0, 140);
    console.log(`ERROR ${p.runtime} ${slug} — ${row.note}`);
    try { await fresh(); } catch {}
  }
}
await browser.close();

const bad = rows.filter(r => r.status !== 'PASS');
console.log(`\n${rows.length - bad.length}/${rows.length} projects fully green (run -> all tests pass -> submit awards XP)`);
if (bad.length) { console.log('FAILURES:'); bad.forEach(r => console.log(`  ${r.rt.padEnd(6)} ${r.slug.padEnd(42)} ${r.verdict ?? ''} ${r.note} ${r.submit ?? ''}`)); }
for (const rt of ['python','sql','web']) {
  const v = rows.filter(r => r.rt === rt && r.bootMs != null).map(r => r.bootMs).sort((a,b)=>a-b);
  const h = rows.filter(r => r.rt === rt && r.hydrateMs != null).map(r => r.hydrateMs).sort((a,b)=>a-b);
  if (v.length) console.log(`${rt}: boot n=${v.length} min=${v[0]} p50=${v[v.length>>1]} max=${v.at(-1)} | page->hydrated p50=${h[h.length>>1]}`);
}
