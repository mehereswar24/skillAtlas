import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
const BASE='http://127.0.0.1:3000';
const REF='C:/Users/Mehereswar/Desktop/skillatlas/backend/app/seed/projects/_reference';
const browser = await chromium.launch();
const page = await (await browser.newContext()).newPage();
page.on('console', m => { if(m.type()==='error') console.log('CONSOLE.ERR:', m.text().slice(0,200)); });
page.on('pageerror', e => console.log('PAGEERR:', String(e).slice(0,200)));
await page.request.post(`${BASE}/api/auth/signup`, { data:{email:`qa${Date.now()}@example.com`,password:'Passw0rd!23'} });

async function trial(slug, files) {
  console.log(`\n===== ${slug} =====`);
  await page.goto(`${BASE}/projects/${slug}`, {waitUntil:'domcontentloaded', timeout:240000});
  await page.evaluate(([s,d])=>localStorage.setItem(`skillatlas-draft:${s}`,JSON.stringify(d)),[slug,files]);
  const t0=Date.now();
  await page.reload({waitUntil:'domcontentloaded', timeout:240000});
  const ok = await page.waitForFunction(()=>{const b=[...document.querySelectorAll('button')].find(x=>/^\s*Run tests\s*$/i.test(x.textContent||''));return !!b&&!b.disabled;},{timeout:200000}).then(()=>true).catch(()=>false);
  console.log('booted', ok, Date.now()-t0,'ms  alert:', await page.locator('[role=alert]').first().innerText().catch(()=>'(none)'));
  if(!ok){ console.log('pill area:', (await page.locator('main').innerText()).split('\n').filter(l=>/Ready|Starting|Runtime|Running/.test(l))); return; }
  // check editor actually has the solution
  const ed = await page.locator('.cm-content').first().innerText().catch(()=>'(no cm)');
  console.log('editor head:', JSON.stringify(ed.slice(0,80)));
  await page.getByRole('button',{name:/^Run tests$/}).click();
  await page.waitForTimeout(15000);
  const t = await page.locator('main').innerText();
  const idx = t.indexOf('Output');
  console.log('--- results ---\n'+t.slice(idx, idx+900));
}
await trial('debounce-and-throttle', {'app.js': readFileSync(`${REF}/debounce-and-throttle/app.js`,'utf8')});
await trial('http-message-parser', {'solution.py': readFileSync(`${REF}/http-message-parser/solution.py`,'utf8')});
await browser.close();
