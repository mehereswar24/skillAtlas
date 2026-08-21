import { chromium } from 'playwright';
const BASE='http://127.0.0.1:3000';
const b=await chromium.launch(); const p=await (await b.newContext()).newPage();
p.setDefaultNavigationTimeout(180000);
p.on('pageerror',e=>console.log('  !! pageerror:', e.message.slice(0,200)));
p.on('console',m=>m.type()==='error'&&console.log('  !! console:', m.text().slice(0,200)));
p.on('framenavigated',f=>f===p.mainFrame()&&console.log('  >> navigated', f.url()));
await p.goto(BASE+'/explore',{waitUntil:'domcontentloaded'});
for (let i=0;i<20;i++){
  const s = await p.evaluate(()=>{
    const i=document.querySelector('input[type=search]');
    const cards=document.querySelectorAll('main button h3').length;
    if(!i) return {input:0,cards};
    const r=i.getBoundingClientRect();
    return {input:1, x:r.x|0,y:r.y|0,w:r.width|0,h:r.height|0, cards};
  }).catch(e=>({err:e.message.slice(0,60)}));
  console.log(`t=${i}s ${JSON.stringify(s)}`);
  await p.waitForTimeout(1000);
}
await b.close();
