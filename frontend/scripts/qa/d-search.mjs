import { chromium } from 'playwright';
const BASE = 'http://127.0.0.1:3000';
const browser = await chromium.launch();
const page = await (await browser.newContext()).newPage();
page.setDefaultNavigationTimeout(180000);
await page.goto(BASE + '/explore', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);

const box = await page.locator('input[type=search]').boundingBox();
const wrapBox = await page.locator('input[type=search]').locator('..').boundingBox();
console.log('input box   ', JSON.stringify(box));
console.log('wrapper box ', JSON.stringify(wrapBox));

// What is actually at the centre of the input?
const at = await page.evaluate(() => {
  const i = document.querySelector('input[type=search]');
  const r = i.getBoundingClientRect();
  const el = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return { tag: el?.tagName, cls: (el?.className || '').toString().slice(0, 80), isInput: el === i };
});
console.log('elementFromPoint at input centre:', JSON.stringify(at));

// Keyboard-only: can you reach the search field with Tab?
await page.goto(BASE + '/explore', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
await page.locator('body').click({ position: { x: 5, y: 5 } });
let reached = -1;
const seq = [];
for (let i = 0; i < 40; i++) {
  await page.keyboard.press('Tab');
  const info = await page.evaluate(() => {
    const a = document.activeElement;
    if (!a) return null;
    const r = a.getBoundingClientRect();
    const cs = getComputedStyle(a);
    return {
      tag: a.tagName, type: a.getAttribute('type'), label: (a.getAttribute('aria-label') || a.innerText || '').trim().slice(0, 30),
      w: Math.round(r.width), h: Math.round(r.height),
      outline: cs.outlineStyle + ' ' + cs.outlineWidth, ring: cs.boxShadow.slice(0, 40),
      visible: r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight,
    };
  });
  seq.push(info);
  if (info && info.type === 'search') { reached = i; break; }
}
console.log('tab sequence:');
seq.forEach((s, i) => console.log(`  ${i}: ${JSON.stringify(s)}`));
console.log('search reached at tab #' + reached);

if (reached >= 0) {
  await page.keyboard.type('design');
  await page.waitForTimeout(800);
  const n = await page.locator('button:has(h3)').count();
  console.log('after typing "design" via keyboard, domain cards: ' + n);
  const w = (await page.locator('input[type=search]').boundingBox()).width;
  console.log('input width while focused: ' + w);
  // Tab away — does the box collapse and hide what was typed?
  await page.keyboard.press('Tab');
  await page.waitForTimeout(900);
  const w2 = (await page.locator('input[type=search]').boundingBox()).width;
  const v = await page.locator('input[type=search]').inputValue();
  console.log(`after blur: width=${w2} value="${v}" cards=${await page.locator('button:has(h3)').count()}`);
}

// --- 375px viewport ---
const m = await (await browser.newContext({ viewport: { width: 375, height: 720 } })).newPage();
m.setDefaultNavigationTimeout(180000);
for (const path of ['/', '/login', '/signup', '/explore']) {
  await m.goto(BASE + path, { waitUntil: 'networkidle' });
  await m.waitForTimeout(1200);
  const o = await m.evaluate(() => ({
    scrollW: document.documentElement.scrollWidth,
    clientW: document.documentElement.clientWidth,
    offenders: [...document.querySelectorAll('body *')]
      .filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 2 && e.getBoundingClientRect().width > 20)
      .slice(0, 6)
      .map(e => e.tagName + '.' + (e.className || '').toString().slice(0, 60) + ' right=' + Math.round(e.getBoundingClientRect().right)),
  }));
  console.log(`375px ${path}: scrollW=${o.scrollW} clientW=${o.clientW} overflow=${o.scrollW > o.clientW + 1}`);
  if (o.offenders.length) o.offenders.forEach(x => console.log('    ' + x));
}
await browser.close();
