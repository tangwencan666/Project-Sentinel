// Observe the already-authorized formal run through the real UI; never create a run or inject a fault.
const {chromium}=require('playwright');const fs=require('node:fs');const path=require('node:path');
const ROOT=path.resolve(__dirname,'..'),OUT=path.join(ROOT,'evaluation','phase4');
const artifact=path.join(OUT,'live-browser-first.json');if(fs.existsSync(artifact))throw Error('Keep first evidence');
const result={started_at:new Date().toISOString(),scope:'READ_ONLY_BROWSER_DURING_REAL_FORMAL_INVESTIGATION',passed:false,mutations:[],errors:[]};
(async()=>{
 let browser;
 try{
  let selected;const deadline=Date.now()+300000;
  while(Date.now()<deadline&&!selected){
   const s=JSON.parse(fs.readFileSync(path.join(ROOT,'evaluation/results/v4.1-first-controlled.json'),'utf8'));
   const r=s.results.findLast(r=>!r.ledger);
   if(r){const i=await (await fetch('http://localhost:18082/api/incidents/'+r.incident_id)).json();if(i.status==='investigating')selected=r}
   if(!selected)await new Promise(resolve=>setTimeout(resolve,2000));
  }
  if(!selected)throw Error('No active formal investigation observed within five minutes');
  result.incident_id=selected.incident_id;result.scenario_operator_only=selected.scenario;
  browser=await chromium.launch({headless:true,channel:'msedge'});const page=await browser.newPage({viewport:{width:1480,height:1100}});
  page.on('request',r=>{if(r.method()==='POST'||r.method()==='DELETE')result.mutations.push(r.url())});page.on('pageerror',e=>result.errors.push(e.message));
  await page.goto('http://localhost:18082/?incident='+selected.incident_id);
  await page.locator('#runtime-diagnostics .runtime-kpis').waitFor();
  await page.waitForFunction(()=>document.querySelector('#sse-status')?.textContent==='SSE LIVE');
  const before=await page.locator('#live-timeline [data-step]').count();result.initial_event_count=before;
  await page.waitForFunction(n=>document.querySelectorAll('#live-timeline [data-step]').length>n,before,{timeout:60000});
  result.final_event_count=await page.locator('#live-timeline [data-step]').count();
  result.observed_status=await page.locator('#live-status').innerText();
  await page.locator('#runtime-diagnostics').screenshot({path:path.join(OUT,'live-runtime-first.png')});
  result.passed=result.final_event_count>before&&!result.mutations.length&&!result.errors.length;
 }catch(e){result.error=e.stack}
 finally{if(browser)await browser.close();result.finished_at=new Date().toISOString();fs.writeFileSync(artifact,JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify(result));if(!result.passed)process.exitCode=1}
})();
