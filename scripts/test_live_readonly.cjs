// Observe the retained local Live workspace with paid capabilities disabled; never mutate it.
const {chromium}=require('playwright');const fs=require('node:fs');const path=require('node:path');
const name=process.argv[2]||'live-workspace-first.json';if(path.basename(name)!==name)throw Error('Use a report filename');
const output=path.resolve(__dirname,'../artifacts/phase5',name);
if(fs.existsSync(output))throw Error('Keep first evidence');
(async()=>{const result={scope:'LOCAL_LIVE_UI_READ_ONLY_AI_DISABLED',errors:[],resource_failures:[],mutations:[],checks:[]};let browser;
try{
 browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||(process.platform==='win32'?'msedge':undefined)});
 const page=await browser.newPage({viewport:{width:1366,height:768}});
 page.on('pageerror',e=>result.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')result.errors.push(m.text())});page.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))result.mutations.push(r.url())});
 page.on('response',r=>{if(r.status()>=400)result.resource_failures.push({url:r.url(),status:r.status()})});
 const base=process.env.SENTINEL_LIVE_URL||'http://localhost:18083';let cfg;
 const deadline=Date.now()+20000;
 while(!cfg){try{const r=await page.request.get(base+'/api/portfolio/config',{timeout:3000});if(r.ok())cfg=await r.json()}catch{}if(!cfg){if(Date.now()>deadline)throw Error('Local service did not become ready');await new Promise(r=>setTimeout(r,500))}}
 if(cfg.live_enabled||cfg.public_demo)throw Error('Expected local stack with AI opt-out');
 await page.goto(base+'/live.html');await page.waitForFunction(()=>document.querySelector('#new-incident')?.disabled===true);
 for(const view of ['overview','incidents','faults','evidence']){await page.locator('nav [data-view="'+view+'"]').click();await page.locator('#'+view+':not(.hidden)').waitFor();result.checks.push(view)}
 await page.locator('nav [data-view="faults"]').click();if(await page.locator('[data-fault]:not(:disabled)').count())throw Error('Fault controls active');
 result.checks.push('fault buttons disabled');
 await page.goto(base+'/live.html?incident=886f2474-3eac-40fa-9368-e3fb829761bc');await page.locator('#runtime-diagnostics .runtime-kpis').waitFor();
 if(!await page.locator('#retry').isDisabled())throw Error('Retry enabled');if(await page.locator('#deploy').count())throw Error('Generic candidate deploy present');
 result.checks.push('recorded incident diagnostics / disabled retry / no generic apply');result.passed=!result.errors.length&&!result.mutations.length&&!result.resource_failures.length;
}catch(e){result.passed=false;result.failure=e.stack}finally{if(browser)await browser.close();fs.writeFileSync(output,JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify(result));if(!result.passed)process.exitCode=1}})();
