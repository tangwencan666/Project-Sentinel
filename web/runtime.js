/* Shared live/recorded rendering; all payload text is escaped. */
window.SentinelRuntime=(()=>{
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const displayLabels=Object.freeze({"RECORDED DEMO": "历史回放（RECORDED DEMO）", "RECORDED SNAPSHOT": "历史快照", "NO LIVE LLM CALLS": "不调用实时模型", "CANDIDATE PATCH": "候选补丁", "NOT DEPLOYED": "尚未部署（NOT DEPLOYED）", "HIGH": "高风险（HIGH）", "HIGH RISK": "高风险（HIGH RISK）", "MEDIUM RISK": "中风险（MEDIUM RISK）", "LOW RISK": "低风险（LOW RISK）", "WORKFLOW COMPLETED": "工作流已完成", "WORKFLOW FAILED": "工作流失败", "REVIEW REQUIRED": "需要人工审阅", "PARTIALLY_VERIFIED": "部分验证（PARTIALLY_VERIFIED）", "VERIFIED": "已验证（VERIFIED）", "CANDIDATE_VERIFIED": "候选已验证（CANDIDATE_VERIFIED）", "AI_GENERATED": "模型生成（AI_GENERATED）", "COMPLETED": "已完成", "CORRECT": "正确", "INCORRECT": "错误", "ROOT CITATION": "根因引用", "V4.1 BENCHMARK": "冻结 V4.1 Benchmark", "LOGS": "日志", "METRICS": "指标", "TRACES": "Trace", "CODE": "源码", "DATABASE": "数据库", "REDIS": "Redis", "KAFKA": "Kafka", "CONTROL": "控制观测", "ALL": "全部", "TRIAGE": "分诊（Triage）", "PLANNER": "计划（Planner）", "TOOL": "工具", "EVIDENCE": "证据", "HYPOTHESIS": "假设", "ROOT CAUSE": "根因", "PATCH": "候选补丁", "TEST": "测试", "CRITIC": "Critic 复核", "RECOVERY": "恢复", "REPAIR": "修复", "ERROR": "错误", "RUNTIME": "Runtime", "CONVERGENCE": "收敛", "Root Cause Proposed": "根因已提交（Root Cause Proposed）", "持久化状态": "持久化状态", "CODE_EXCEPTION": "代码异常（CODE_EXCEPTION）", "Live AI investigation is disabled in the public demo. Run Sentinel locally to enable live investigation.": "公开演示已禁用实时 AI 调查。需要本地运行并显式启用 Live Lab。", "Local Live AI requires explicit LIVE_AI_ENABLED=true and configured provider credentials.": "本地实时调查需要 LIVE_AI_ENABLED=true 与模型配置。"});
const displayText=value=>Object.hasOwn(displayLabels,value)?displayLabels[value]:value;
 const num=n=>n==null?"未知":Number(n).toLocaleString(undefined,{maximumFractionDigits:2});
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
  return `<div class="table-scroll runtime-table"><table><thead><tr><th>Agent / 轮次</th><th>原始字符</th><th>编译后字符</th><th>编译/原始</th><th>保留/遗漏</th><th>固定状态字符</th><th>Provider 输入 Token</th></tr></thead><tbody>${(rows||[]).slice(0,12).map(r=>{const t=r.telemetry||{};return `<tr><td>${esc(r.agent)} / ${num(t.round)}</td><td>${num(t.raw_context_size)}</td><td>${num(t.compiled_context_size)}</td><td>${t.compression_ratio==null?"未知":num(t.compression_ratio*100)+'%'}</td><td>${num(t.evidence_retained?.length)} / ${num(t.evidence_dropped?.length)}</td><td>${num(t.pinned_context_size)}</td><td>${num(t.provider_input_tokens)}</td></tr>`}).join('')}</tbody></table></div>`;
 }
 function providers(calls){return `<details class="step"><summary>Provider 诊断：结束原因、解析与 schema</summary><div class="table-scroll runtime-table"><table><thead><tr><th>角色</th><th>传输状态</th><th>结束原因</th><th>解析状态</th><th>输入/输出</th></tr></thead><tbody>${(calls||[]).map(c=>`<tr><td>${esc(c.agent)}</td><td>${esc(c.status)}</td><td>${esc(c.diagnostics?.finish_reason||"未知")}</td><td>${esc(c.diagnostics?.parse_status||"未知")}</td><td>${num(c.input_tokens)} / ${num(c.output_tokens)}</td></tr>`).join('')}</tbody></table></div><pre>${esc(JSON.stringify((calls||[]).filter(c=>c.error||c.diagnostics?.parse_error||c.diagnostics?.schema_error).map(c=>({id:c.id,error:c.error,diagnostics:c.diagnostics})),null,2))}</pre></details>`}
 function render(target,data){
  const count=kind=>(data.event_counts||[]).find(e=>e.kind===kind)?.count??0;
  target.innerHTML=`<div class="panel-head"><h2>Runtime 诊断</h2><span class="tag measured">持久化状态</span></div><div class="runtime-body"><div class="runtime-kpis">${[["阶段",data.checkpoint?.phase||"不可用"],["上下文重建",count('Context Rebuilt')],["固定错误",Object.keys(data.pinned_errors||{}).length],["schema 修复",count('Schema Repair')],["Checkpoint 恢复",data.resume_count??"未知"],["已读证据",data.read_registry_count??"未知"]].map(([k,v])=>`<div><small>${k}</small><b>${esc(v)}</b></div>`).join('')}</div>
  ${data.legacy_state_unavailable?'<p class="muted">此旧版本未保存完整 typed runtime state，缺失值不视为零。</p>':''}
  <div class="runtime-budgets">${(data.budgets||[]).map(b=>`<div><label>${esc(b.name)} <span>${num(b.used)} / ${num(b.limit)}</span></label><meter value="${Number(b.used)}" max="${Number(b.limit)}"></meter></div>`).join('')}</div>
  <details class="step" ${Object.keys(data.pinned_errors||{}).length?'open':''}><summary>P0：校验错误与缺失条件</summary><pre>${esc(JSON.stringify({errors:data.pinned_errors,missing:data.missing_requirements,last_error:data.last_error},null,2))}</pre></details>
  <details class="step"><summary>P1：假设、关键证据与待执行动作</summary><pre>${esc(JSON.stringify({hypotheses:data.active_hypotheses,evidence_ids:data.critical_evidence_ids,unfinished_tools:data.unfinished_tools},null,2))}</pre></details>
  <details class="step"><summary>Runtime 事件：修复、熔断与恢复</summary><pre>${esc(JSON.stringify(data.event_counts,null,2))}</pre></details>
  ${compression(data.context_measurements)}${providers(data.provider_calls)}<p class="muted">${esc(data.measurement_note)}</p></div>`;
 }
 return {stage,render,compression,providers,displayText};
})();
