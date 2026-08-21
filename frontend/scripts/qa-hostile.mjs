import { chromium } from 'playwright';
const BASE='http://127.0.0.1:3000';
const browser = await chromium.launch();
const page = await (await browser.newContext()).newPage();
page.on('pageerror', e=>console.log('  PAGEERR:', String(e).slice(0,160)));
await page.request.post(`${BASE}/api/auth/signup`, {data:{email:`qa${Date.now()}@example.com`,password:'Passw0rd!23'}});

async function open(slug, files) {
  await page.goto(`${BASE}/projects/${slug}`, {waitUntil:'domcontentloaded', timeout:240000});
  await page.evaluate(([s,d])=>localStorage.setItem(`skillatlas-draft:${s}`,JSON.stringify(d)),[slug,files]);
  await page.reload({waitUntil:'domcontentloaded', timeout:240000});
  const ok = await page.waitForFunction(()=>{const b=[...document.querySelectorAll('button')].find(x=>/^\s*Run tests\s*$/i.test(x.textContent||''));return !!b&&!b.disabled;},{timeout:200000}).then(()=>true).catch(()=>false);
  await page.waitForTimeout(1000);
  return ok;
}
const results = t => page.locator('main').innerText().then(x=>{const i=x.indexOf('Output');return i<0?'(no results panel)':x.slice(i,i+t);});

// ---- 1. Python infinite loop + Stop -------------------------------------
console.log('\n### 1. python infinite loop -> Stop');
let t0=Date.now();
console.log(' boot', await open('http-message-parser', {'solution.py':'while True:\n    pass\n'}), Date.now()-t0,'ms');
await page.getByRole('button',{name:/^Run tests$/}).click();
await page.waitForTimeout(3000);
const stopVisible = await page.getByRole('button',{name:/^Stop$/}).isVisible().catch(()=>false);
console.log(' Stop button visible while looping:', stopVisible);
// is the page still responsive?
t0=Date.now();
const responsive = await page.evaluate(()=>1+1).then(v=>v===2).catch(()=>false);
console.log(' main thread responsive:', responsive, Date.now()-t0,'ms');
if (stopVisible) {
  t0=Date.now();
  await page.getByRole('button',{name:/^Stop$/}).click();
  await page.waitForTimeout(1500);
  console.log(' after Stop, results:', JSON.stringify((await results(200)).replace(/\n/g,' | ')));
  const reready = await page.waitForFunction(()=>{const b=[...document.querySelectorAll('button')].find(x=>/^\s*Run tests\s*$/i.test(x.textContent||''));return !!b&&!b.disabled;},{timeout:200000}).then(()=>true).catch(()=>false);
  console.log(' re-ready after Stop:', reready, Date.now()-t0,'ms  <-- time before learner can run again');
}

// ---- 2. Python syntax error --------------------------------------------
console.log('\n### 2. python syntax error');
await open('http-message-parser', {'solution.py':'def parse_request(raw:\n    return {'});
await page.getByRole('button',{name:/^Run tests$/}).click();
await page.waitForTimeout(6000);
console.log(JSON.stringify((await results(400)).replace(/\n/g,' | ')));

// ---- 3. Python empty file ----------------------------------------------
console.log('\n### 3. python empty file');
await open('http-message-parser', {'solution.py':''});
await page.getByRole('button',{name:/^Run tests$/}).click();
await page.waitForTimeout(8000);
console.log(JSON.stringify((await results(400)).replace(/\n/g,' | ')));

// ---- 4. Enormous output -------------------------------------------------
console.log('\n### 4. python enormous output (20M chars)');
await open('http-message-parser', {'solution.py':'for _ in range(200000):\n    print("x"*100)\n\ndef parse_request(raw):\n    return {}\n'});
t0=Date.now();
await page.getByRole('button',{name:/^Run tests$/}).click();
const got = await page.waitForFunction(()=>/passing/.test(document.body.innerText),{timeout:180000}).then(()=>true).catch(()=>false);
console.log(' finished:', got, Date.now()-t0,'ms');
const outLen = await page.evaluate(()=>{const p=[...document.querySelectorAll('pre')][0];return p?p.innerText.length:-1;});
console.log(' output <pre> length:', outLen);
t0=Date.now(); await page.evaluate(()=>1+1); console.log(' responsiveness after:', Date.now()-t0,'ms');

await browser.close();
