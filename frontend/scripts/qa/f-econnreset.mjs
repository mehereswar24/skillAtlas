const BASE='http://127.0.0.1:8011';
// Next renders / with Promise.all of 3 fetches, repeatedly, over one agent.
async function round(){
  const paths=['/api/v1/domains','/api/v1/tracks','/api/v1/auth/me'];
  const rs = await Promise.allSettled(paths.map(p=>fetch(BASE+p,{cache:'no-store'}).then(r=>r.arrayBuffer())));
  return rs.map(r=>r.status==='fulfilled'?'ok':(r.reason?.cause?.code||r.reason?.message));
}
let bad=0;
for(let i=0;i<40;i++){
  const r = await round();
  const b = r.filter(x=>x!=='ok');
  if(b.length){ bad++; console.log(`round ${i}:`, r.join(',')); }
}
console.log(`bad rounds: ${bad}/40`);

// Now with high concurrency, as several page renders at once
console.log('--- 20 concurrent page-shaped rounds ---');
const res = await Promise.all(Array.from({length:20},()=>round()));
const flat = res.flat();
console.log('failures:', flat.filter(x=>x!=='ok').slice(0,10), 'of', flat.length);
