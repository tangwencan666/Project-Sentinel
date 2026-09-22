// Read-only browser checks for the completed first release suite. No model or fault dispatch.
const {chromium}=require('playwright');
const fs=require('node:fs');const path=require('node:path');
const ROOT=path.resolve(__dirname,'..'),OUT=path.join(ROOT,'evaluation','phase4');
const name=process.argv[2]||'release-browser-first.json';
if(path.basename(name)!==name||fs.existsSync(path.join(OUT,name)))throw Error('Use a new evidence filename');
const expected=JSON.parse(fs.readFileSync(path.join(OUT,'final-release-report.json'),'utf8'));
if(expected.status!=='completed'||expected.version.results.length!==8)throw Error('Wait for the complete first suite');
const result={started_at:new Date().toISOString(),scope:'REAL_BROWSER_COMPLETED_RELEASE_READ_ONLY',checks:[],mutations:[],errors:[]};
(async()=>{
 let browser,page;
 try{
  browser=await chromium.launch({headless:true,channel:'msedge'});
  page=await browser.newPage({viewport:{width:1480,height:1000}});
  page.on('request',r=>{if(!['GET','HEAD','OPTIONS'].includes(r.method()))result.mutations.push(r.method()+' '+r.url())});
  page.on('pageerror',e=>result.errors.push(e.message));
  async function check(name,fn){await fn();result.checks.push({name,passed:true})}
  await page.goto('http://localhost:18082/evaluation.html');
  await check('live release API equals persisted first-run report',async()=>{
   const response=await page.request.get('http://localhost:18082/api/release-evaluation');
   if(!response.ok())throw Error('Release endpoint failed');
   const actual=await response.json();
   if(JSON.stringify(actual)!==JSON.stringify(expected))throw Error('API/file mismatch');
  });
  await check('eight release outcomes and six historical versions remain separate',async()=>{
   await page.locator('[data-release-run]').nth(7).waitFor();
   if(await page.locator('[data-release-run]').count()!==8||await page.locator('#version-cards .eval-card').count()!==6)throw Error('Cohort counts differ');
   const text=await page.locator('#release-results').innerText(),m=expected.version.metrics;
   if(!text.includes('Workflow '+m.workflow_completed+'/8')||!text.includes('sentinel-benchmark-v2'))throw Error('Release metrics absent');
   for(const r of expected.version.results){
    const button=page.locator('[data-release-run="'+r.run_id+'"]');
    const text=await button.innerText();
    if(!text.includes(r.scenario)||!text.includes(r.workflow_completed?'Completed':'Failed')||!text.includes(r.correct?'Correct':'Incorrect'))throw Error('Outcome mismatch: '+r.scenario);
   }
  });
  await page.locator('#release-results').screenshot({path:path.join(OUT,'release-results-first.png')});
  await check('release recorded run exposes actual measurements and advances without mutations',async()=>{
   const r=expected.version.results.find(x=>x.scenario==='code_exception');
   await page.locator('[data-release-run="'+r.run_id+'"]').click();
   await page.locator('#run-detail:not(.hidden)').waitFor();
   if(!(await page.locator('#run-title').innerText()).includes('Final Runtime V4.1 / code_exception'))throw Error('Wrong replay');
   if(!(await page.locator('#recorded-diagnostics').innerText()).includes('finish'))throw Error('Provider diagnostics absent');
   if(await page.locator('#run-measurements tbody tr').count()<2)throw Error('Before/after measurements absent');
   await page.locator('#replay-start').click();
   await page.waitForFunction(()=>Number(document.querySelector('#replay-cursor').value)>=2);
   await page.locator('#replay-pause').click();
   if(!(await page.locator('#replay-progress').innerText()).includes('RECORDED RUN'))throw Error('Replay label absent');
  });
  await page.locator('#run-detail').screenshot({path:path.join(OUT,'release-replay-first.png')});
  await page.setViewportSize({width:390,height:844});await page.goto('http://localhost:18082/evaluation.html');
  await page.locator('[data-release-run]').nth(7).waitFor();
  await check('completed release mobile layout fits viewport',async()=>{
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Mobile overflow');
  });
  result.passed=!result.errors.length&&!result.mutations.length;
 }catch(e){result.passed=false;result.failure=e.stack}
 finally{if(browser)await browser.close();result.finished_at=new Date().toISOString();fs.writeFileSync(path.join(OUT,name),JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify(result));if(!result.passed)process.exitCode=1}
})();
