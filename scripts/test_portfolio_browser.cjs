// Real Edge + live read-only API. Explicit UI fault fixtures are isolated from real-data checks.
const {chromium}=require('playwright');const fs=require('node:fs');const path=require('node:path');
const ROOT=path.resolve(__dirname,'..'),OUT=path.join(ROOT,'artifacts','phase5'),SHOTS=path.join(ROOT,'docs','screenshots');
const output=process.argv[2]||'browser-first.json';if(path.basename(output)!==output||fs.existsSync(path.join(OUT,output)))throw Error('Preserve previous evidence; choose a new filename');
const BASE=process.env.SENTINEL_DEMO_URL||'http://localhost:18082';
const result={scope:'REAL_BROWSER_REAL_RECORDED_API',started_at:new Date().toISOString(),checks:[],errors:[],resource_failures:[],mutations:[],performance:[],screenshots:[]};
const pages=['','incident','replay','evidence','root-cause','patch','evaluation','architecture','documentation'];
(async()=>{let browser;try{
 browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||(process.platform==='win32'?'msedge':undefined)});const context=await browser.newContext();const page=await context.newPage();
 page.on('pageerror',e=>result.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')result.errors.push(m.text())});
 page.on('response',r=>{if(r.status()>=400)result.resource_failures.push({url:r.url(),status:r.status()})});
 page.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))result.mutations.push(r.method()+' '+r.url())});
 async function check(name,fn){await fn();result.checks.push({name,passed:true})}
 async function visit(name){const started=Date.now();await page.goto(BASE+'/'+(name?name+'.html':''));await page.locator('#content h1').first().waitFor();if((await page.locator('#content h1').first().innerText()).includes('unavailable'))throw Error('Page failed: '+name);result.performance.push({page:name||'dashboard',ms:Date.now()-started})}
 for(const size of [{width:1366,height:768},{width:1920,height:1080},{width:390,height:844}]){
  await page.setViewportSize(size);
  for(const name of pages)await check((name||'dashboard')+' renders without overflow '+size.width,async()=>{await visit(name);if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Overflow '+name+' at '+size.width)});
 }
 await page.setViewportSize({width:1366,height:768});await visit('');
 await check('mode notice explains disabled live and provenance loads',async()=>{
  await page.locator('#mode-info').click();if(!(await page.locator('#modal').innerText()).includes('disabled in the public demo'))throw Error('Mode message missing');await page.getByRole('button',{name:'Close dialog'}).click();
  await page.locator('[data-action="provenance"]').click();await page.locator('#modal[open] pre').waitFor();if(!(await page.locator('#modal').innerText()).includes('759044e6-c016-489b-a459-137ca4846462'))throw Error('Wrong provenance');await page.getByRole('button',{name:'Close dialog'}).click();
 });
 await check('real replay play pause restart speeds root and event details',async()=>{
  await visit('replay');await page.locator('[data-action="play"]').click();await page.waitForFunction(()=>parseInt(document.querySelector('#event-count').textContent)>0);
  await page.locator('#speed').selectOption('2');await page.locator('#speed').selectOption('4');await page.locator('#speed').selectOption('1');
  await page.locator('[data-action="pause"]').click();const paused=await page.locator('#event-count').innerText();await page.waitForTimeout(250);if(await page.locator('#event-count').innerText()!==paused)throw Error('Pause moved cursor');
  await page.locator('[data-action="restart"]').click();if(!(await page.locator('#replay-state').innerText()).includes('00:00'))throw Error('Restart failed');
  await page.locator('[data-action="root"]').click();const brief=await page.locator('#timeline li').count();await page.locator('#audit-events').check();if(await page.locator('#timeline li').count()<brief)throw Error('Audit event toggle');await page.locator('#audit-events').uncheck();if(!(await page.locator('#timeline').innerText()).includes('Root Cause Proposed'))throw Error('Skip root failed');
  await page.locator('[data-action="event"]').last().click();await page.locator('#modal[open] pre').waitFor();if(!(await page.locator('#modal').innerText()).includes('Root Cause Proposed'))throw Error('Raw event differs');await page.getByRole('button',{name:'Close dialog'}).click();
 });
 await check('evidence is lazy and every source filter works',async()=>{
  await page.reload();let raws=0;const listener=r=>{if(r.url().includes('/api/portfolio/evidence/'))raws++};page.on('request',listener);
  await visit('evidence');if(raws)throw Error('Eager raw evidence');
  for(const group of ['LOGS','METRICS','TRACES','CODE','DATABASE','REDIS','KAFKA','CONTROL','ALL']){await page.locator('[data-filter="'+group+'"]').click();if(await page.locator('[data-filter].selected').count()!==1)throw Error('Filter selection');}
  await page.locator('details[data-raw]').first().locator('summary').click();await page.locator('.raw-content pre').first().waitFor();if(raws!==1)throw Error('Raw loading count '+raws);page.off('request',listener);
 });
 await check('root evidence links and report download work',async()=>{await visit('root-cause');await page.locator('[data-action="evidence"]').first().click();await page.locator('#modal pre').waitFor();await page.getByRole('button',{name:'Close dialog'}).click();const response=await page.request.get(BASE+'/api/portfolio/report');if(!response.ok()||!(await response.text()).includes('NOT DEPLOYED'))throw Error('Report invalid')});
 await check('candidate diff tests replay and disabled apply are truthful',async()=>{await visit('patch');if(!(await page.locator('#patch-diff').innerText()).includes('+    if discount is None:'))throw Error('Diff absent');if(!await page.getByRole('button',{name:/Apply patch/}).isDisabled())throw Error('Apply enabled');for(const d of await page.locator('details').all())await d.locator('summary').click();const response=await page.request.get(BASE+'/api/portfolio/patch.diff');if(!response.ok())throw Error('Diff download')});
 await check('all 56 historical outcome buttons open genuine retained records',async()=>{await visit('evaluation');const buttons=page.locator('#scenario-matrix button');if(await buttons.count()!==56)throw Error('Expected 7 x 8 records');for(let i=0;i<56;i++){await buttons.nth(i).click();await page.locator('#modal[open] h2').waitFor();if(!(await page.locator('#modal h2').innerText()).includes('RECORDED RUN'))throw Error('History failed');await page.getByRole('button',{name:'Close dialog'}).click()}});
 await check('all portfolio document links resolve',async()=>{await visit('documentation');const urls=await page.locator('.doc-list a').evaluateAll(as=>as.map(a=>a.href));for(const url of urls){await page.goto(url);await page.locator('.document').waitFor();if((await page.locator('.document').innerText()).length<100)throw Error('Empty document')}});
 await check('document headings tables anchors and original download work',async()=>{
  await visit('documentation');await page.locator('.document table').first().waitFor();await page.locator('.doc-contents summary').click();await page.locator('.doc-anchor-list a[href="#security"]').click();if(new URL(page.url()).hash!=='#security')throw Error('Document anchor failed');
  const received=page.waitForEvent('download');await page.locator('[data-action="download-document"]').click();const download=await received;if(download.suggestedFilename()!=='README.md')throw Error('Wrong Markdown filename');const text=fs.readFileSync(await download.path(),'utf8');if(text!==fs.readFileSync(path.join(ROOT,'README.md'),'utf8').replace(/\r\n/g,'\n'))throw Error('Markdown download changed');
  await page.locator('.document a[href="/documentation.html?doc=docs%2Fdemo-5min.md"]').first().click();await page.locator('.document h1').waitFor();if(!page.url().includes('demo-5min.md'))throw Error('Relative documentation link failed');
  const report=await page.request.get(BASE+'/api/portfolio/verification');if(!report.ok()||(await report.json()).cost.phase5_real_llm_calls!==0)throw Error('Verification download unavailable');
 });
 await check('interview document remains readable on narrow screen',async()=>{
  await page.setViewportSize({width:390,height:844});await page.goto(BASE+'/documentation.html?doc=docs%2Finterview-qa.md');await page.locator('.document h2').first().waitFor();if(await page.locator('.document h2').count()!==49)throw Error('Missing interview questions');if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Document overflow');await page.screenshot({path:path.join(OUT,'mobile-documentation.png'),fullPage:true});
 });
 // Screenshots of real data only; test fixtures below never enter screenshots.
 await page.setViewportSize({width:1920,height:1080});
 for(const [name,file] of [['','dashboard'],['replay','investigation-replay'],['evidence','evidence'],['root-cause','root-cause'],['patch','ai-patch'],['evaluation','evaluation'],['architecture','architecture']]){
  await visit(name);if(name==='replay')await page.locator('[data-action="root"]').click();
  const target=path.join(SHOTS,file+'.png');await page.screenshot({path:target,fullPage:true});result.screenshots.push('docs/screenshots/'+file+'.png');
  if(!name){await page.locator('#topology').screenshot({path:path.join(SHOTS,'service-topology.png')});result.screenshots.push('docs/screenshots/service-topology.png')}
 }
 await page.setViewportSize({width:390,height:844});await visit('');await page.screenshot({path:path.join(OUT,'mobile-dashboard.png'),fullPage:true});
 // Dedicated browser fixture verifies error/loading/empty UX without altering server data.
 await check('labelled frontend-only error loading and empty fixtures',async()=>{
  const isolated=await browser.newContext();const p=await isolated.newPage();
  await p.route('**/api/portfolio/demo',route=>route.fulfill({status:503,contentType:'application/json',body:'{"detail":"UI_TEST_FIXTURE"}'}));
  await p.goto(BASE+'/');await p.getByRole('heading',{name:'Recorded demo unavailable'}).waitFor();await p.getByRole('button',{name:'Retry',exact:true}).click();await p.getByRole('heading',{name:'Recorded demo unavailable'}).waitFor();
  await p.unroute('**/api/portfolio/demo');const actual=await (await page.request.get(BASE+'/api/portfolio/demo')).json();
  let release;const gate=new Promise(resolve=>release=resolve);
  await p.route('**/api/portfolio/demo',async route=>{await gate;await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({...actual,evidence:[]})})});
  await p.goto(BASE+'/evidence.html');await p.locator('.loading').waitFor();release();await p.locator('#evidence-grid .empty').waitFor();await isolated.close();
 });
 result.passed=!result.errors.length&&!result.resource_failures.length&&!result.mutations.length;
}catch(e){result.passed=false;result.failure=e.stack}finally{if(browser)await browser.close();result.finished_at=new Date().toISOString();fs.writeFileSync(path.join(OUT,output),JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify(result));if(!result.passed)process.exitCode=1}})();
