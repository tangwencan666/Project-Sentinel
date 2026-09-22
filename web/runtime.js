/* Shared live/recorded rendering; all payload text is escaped. */
window.SentinelRuntime=(()=>{
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const num=n=>n==null?'Unknown':Number(n).toLocaleString(undefined,{maximumFractionDigits:2});
 function stage(kind){
  const k=String(kind).toLowerCase();
  if(/repair|fallback/.test(k))return 'REPAIR';
  if(/error|failed|breaker/.test(k))return 'ERROR';
  if(/triage/.test(k))return 'TRIAGE';if(/planner|planning/.test(k))return 'PLANNER';
  if(/hypothesis/.test(k))return 'HYPOTHESIS';if(/root|decision/.test(k))return 'ROOT CAUSE';
  if(/critic|verification/.test(k))return 'CRITIC';if(/test|replay|candidate/.test(k))return 'TEST';
  if(/patch/.test(k))return 'PATCH';if(/convergence|phase/.test(k))return 'CONVERGENCE';
  if(/evidence/.test(k))return 'EVIDENCE';if(/tool/.test(k))return 'TOOL';
  return 'RUNTIME';
 }
 function compression(rows){
  return `<div class="table-scroll runtime-table"><table><thead><tr><th>Agent / round</th><th>Raw chars</th><th>Compiled chars</th><th>Compiled / raw</th><th>Retained / dropped</th><th>Pinned chars</th><th>Provider input tokens</th></tr></thead><tbody>${(rows||[]).slice(0,12).map(r=>{const t=r.telemetry||{};return `<tr><td>${esc(r.agent)} / ${num(t.round)}</td><td>${num(t.raw_context_size)}</td><td>${num(t.compiled_context_size)}</td><td>${t.compression_ratio==null?'Unknown':num(t.compression_ratio*100)+'%'}</td><td>${num(t.evidence_retained?.length)} / ${num(t.evidence_dropped?.length)}</td><td>${num(t.pinned_context_size)}</td><td>${num(t.provider_input_tokens)}</td></tr>`}).join('')}</tbody></table></div>`;
 }
 function providers(calls){return `<details class="step"><summary>Provider diagnostics · finish reason / parse / schema</summary><div class="table-scroll runtime-table"><table><thead><tr><th>Actor</th><th>Transport</th><th>Finish</th><th>Parse</th><th>Input / output</th></tr></thead><tbody>${(calls||[]).map(c=>`<tr><td>${esc(c.agent)}</td><td>${esc(c.status)}</td><td>${esc(c.diagnostics?.finish_reason||'Unknown')}</td><td>${esc(c.diagnostics?.parse_status||'Unknown')}</td><td>${num(c.input_tokens)} / ${num(c.output_tokens)}</td></tr>`).join('')}</tbody></table></div><pre>${esc(JSON.stringify((calls||[]).filter(c=>c.error||c.diagnostics?.parse_error||c.diagnostics?.schema_error).map(c=>({id:c.id,error:c.error,diagnostics:c.diagnostics})),null,2))}</pre></details>`}
 function render(target,data){
  const count=kind=>(data.event_counts||[]).find(e=>e.kind===kind)?.count??0;
  target.innerHTML=`<div class="panel-head"><h2>Runtime Diagnostics</h2><span class="tag measured">DURABLE STATE</span></div><div class="runtime-body"><div class="runtime-kpis">${[['Phase',data.checkpoint?.phase||'Unavailable'],['Context rebuilds',count('Context Rebuilt')],['Pinned errors',Object.keys(data.pinned_errors||{}).length],['Schema repairs',count('Schema Repair')],['Checkpoint resumes',data.resume_count??'Unknown'],['Read evidence',data.read_registry_count??'Unknown']].map(([k,v])=>`<div><small>${k}</small><b>${esc(v)}</b></div>`).join('')}</div>
  ${data.legacy_state_unavailable?'<p class="muted">此旧版本未保存完整 typed runtime state，缺失值不视为零。</p>':''}
  <div class="runtime-budgets">${(data.budgets||[]).map(b=>`<div><label>${esc(b.name)} <span>${num(b.used)} / ${num(b.limit)}</span></label><meter value="${Number(b.used)}" max="${Number(b.limit)}"></meter></div>`).join('')}</div>
  <details class="step" ${Object.keys(data.pinned_errors||{}).length?'open':''}><summary>P0 · Validation errors / missing requirements</summary><pre>${esc(JSON.stringify({errors:data.pinned_errors,missing:data.missing_requirements,last_error:data.last_error},null,2))}</pre></details>
  <details class="step"><summary>P1 · Hypotheses / critical evidence / unfinished actions</summary><pre>${esc(JSON.stringify({hypotheses:data.active_hypotheses,evidence_ids:data.critical_evidence_ids,unfinished_tools:data.unfinished_tools},null,2))}</pre></details>
  <details class="step"><summary>Runtime events · repair / breaker / resume</summary><pre>${esc(JSON.stringify(data.event_counts,null,2))}</pre></details>
  ${compression(data.context_measurements)}${providers(data.provider_calls)}<p class="muted">${esc(data.measurement_note)}</p></div>`;
 }
 return {stage,render,compression,providers};
})();
