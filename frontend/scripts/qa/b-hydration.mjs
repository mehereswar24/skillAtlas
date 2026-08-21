// Does the auth form do a native GET submit before React hydrates?
// If so, the password ends up in the URL / browser history.
import { chromium } from 'playwright';
const BASE = 'http://127.0.0.1:3000';
const browser = await chromium.launch();

for (const mode of ['signup', 'login']) {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  page.setDefaultNavigationTimeout(180000);
  // Block the JS chunks so the page can never hydrate — simulates the
  // real-world window between HTML paint and hydration on a slow client.
  await page.route('**/_next/static/chunks/**', r => r.abort());
  await page.goto(`${BASE}/${mode}`, { waitUntil: 'domcontentloaded' });
  await page.fill('#email', 'victim@example.com');
  await page.fill('#password', 'hunter2-SuperSecret');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(2500);
  const url = page.url();
  console.log(`${mode}: ${url}`);
  console.log(`   password in URL? ${url.includes('hunter2') ? 'YES — LEAK' : 'no'}`);
  await ctx.close();
}
await browser.close();
