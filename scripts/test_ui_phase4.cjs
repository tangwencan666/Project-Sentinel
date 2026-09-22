// Actual Chromium + live application. No mocked APIs or injected evaluation results.
const {chromium}=require('playwright');
const fs=require('node:fs');const path=require('node:path');
const ROOT=path.resolve(__dirname,'..'),OUT=path.join(ROOT,'evaluation','phase4');
const output=process.argv[2]||'ui-e2e-first.json';
if(path.basename(output)!==output||fs.existsSync(path.join(OUT,output)))throw Error('Use a new result filename');
const ART=path.join(OUT,output.replace(/\.json$/,''));fs.mkdirSync(ART,{recursive:true});
const result={artifact_directory:ART,scope:'REAL_BROWSER_LIVE_API_NO_MOCKS',started_at:new Date().toISOString(),checks:[],errors:[]};
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});const context=await browser.newContext({viewport:{width:1480,height:980}});const page=await context.newPage();
 page.on('pageerror',e=>result.errors.push(e.message));
 async function check(name,fn){await fn();result.checks.push({name,passed:true})}
 try{
  await page.goto('http://localhost:18082/evaluation.html');
  await check('six historic versions and honest V3/V3.1 workflow counts',async()=>{
   await page.locator('#version-cards .eval-card').nth(5).waitFor();
   if(await page.locator('#version-cards .eval-card').count()!==6)throw Error('Expected six historical versions');
   const text=await page.locator('#version-cards').innerText();
   if(!text.includes('2 / 8')||!text.includes('1 / 8')||!text.includes('fixture confounds'))throw Error('Historical failures/confounds absent');
  });
  await page.screenshot({path:path.join(ART,'ui-evaluation-desktop.png'),fullPage:true});
  await check('recorded replay advances without dispatching a model',async()=>{
   let mutations=[];page.on('request',r=>{if(r.method()==='POST')mutations.push(r.url())});
   await page.locator('.matrix-cell.confounded').first().click();
   await page.locator('#run-detail:not(.hidden)').waitFor();
   if(!(await page.locator('#failure-analysis').innerText()).includes('consumer'))throw Error('Confound detail absent');
   await page.locator('#replay-start').click();
   await page.waitForFunction(()=>Number(document.querySelector('#replay-cursor').value)>=2);
   await page.locator('#replay-pause').click();
   if(mutations.length)throw Error('Replay issued mutation');
   if(!(await page.locator('#replay-progress').innerText()).includes('RECORDED RUN'))throw Error('Replay not labelled');
  });
  const recovery=JSON.parse(fs.readFileSync(path.join(OUT,'crash-resume-followup.json'),'utf8'));
  await page.goto('http://localhost:18082/?incident='+recovery.result.incident_id);
  await check('live checkpoint diagnostics and candidate review',async()=>{
   await page.locator('#runtime-diagnostics .runtime-kpis').waitFor();
   if(!(await page.locator('#runtime-diagnostics').innerText()).includes('Checkpoint resumes'))throw Error('Diagnostics missing');
   if(await page.locator('#deploy').count())throw Error('Generic candidate incorrectly offers live deploy');
   await page.locator('details.step').filter({hasText:'PATCH ·'}).first().locator('summary').click();
   await page.getByRole('link',{name:'导出候选 Diff'}).waitFor();
   const href=await page.getByRole('link',{name:'导出候选 Diff'}).getAttribute('href');
   const response=await context.request.get('http://localhost:18082'+href);
   if(!response.ok()||!(await response.text()).includes('--- a/services/pricing.py'))throw Error('Candidate export failed');
   const d=await (await context.request.get('http://localhost:18082/api/incidents/'+recovery.result.incident_id+'/runtime')).json();
   if(d.resume_count!==1||d.checkpoint.phase!=='COMPLETED')throw Error('Displayed recovery state differs');
  });
  await page.locator('#runtime-diagnostics').screenshot({path:path.join(ART,'ui-runtime-diagnostics.png')});
  await page.goto('http://localhost:18082/architecture.html');
  await check('architecture shows implemented trust boundaries',async()=>{
   if(await page.locator('.architecture-flow article').count()!==9)throw Error('Architecture cards missing');
   if(!(await page.locator('main').innerText()).includes('Ground Truth'))throw Error('Truth boundary missing');
  });
  await page.setViewportSize({width:390,height:844});await page.goto('http://localhost:18082/evaluation.html');
  await page.locator('#version-cards .eval-card').nth(5).waitFor();
  await check('mobile has no page-level horizontal overflow',async()=>{
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Mobile page overflow');
  });
  await page.screenshot({path:path.join(ART,'ui-evaluation-mobile.png'),fullPage:true});
  result.passed=result.errors.length===0;
 }catch(e){result.passed=false;result.failure=e.stack;await page.screenshot({path:path.join(ART,'ui-failure.png'),fullPage:true}).catch(()=>{})}
 finally{await browser.close();result.finished_at=new Date().toISOString();fs.writeFileSync(path.join(OUT,output),JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify(result));if(!result.passed)process.exitCode=1}
})();
