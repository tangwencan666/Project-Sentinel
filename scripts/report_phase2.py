"""Derive delivery metrics from stored runs. Does not re-score or overwrite raw results."""
import json
import statistics
import subprocess
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from evaluate_phase2 import api,aggregates

root=Path(__file__).resolve().parents[1]
raw=json.loads((root/'docs/phase2-evaluation-v3.json').read_text(encoding='utf-8'))
results=raw['results']
if len(results)!=16 or len({(r['scenario'],r['mode']) for r in results})!=16:
    raise RuntimeError('Wait for the complete eight-scenario, two-mode frozen evaluation before reporting.')
ledger=[]
for r in results:
    data=api('/incidents/'+r['incident_id']+'/agent')
    incident=api('/incidents/'+r['incident_id'])
    run_id=r.get('run_id') or incident.get('investigation_run')
    calls=[c for c in data['tool_calls'] if c['run_id']==run_id]
    llm=[c for c in data['usage']['calls'] if c['run_id']==run_id]
    patches=[p for p in data['patches'] if p['run_id']==run_id]
    recovery=(incident.get('report') or {}).get('measured_recovery')
    ledger.append({'scenario':r['scenario'],'mode':r['mode'],'incident_id':r['incident_id'],'run_id':run_id,'status':incident['status'],'run_errors':[x.get('error') for x in data['runs'] if x['id']==run_id and x.get('error')],'llm_calls':llm,'tool_calls':calls,'evidence':data['evidence'],'hypotheses':data.get('hypotheses',[]),'patches':patches,'measured_recovery':recovery,'steps':incident['steps'],'report':incident.get('report')})
    r['patch_requested']=((incident.get('report') or {}).get('diagnosis') or {}).get('patch_decision')=='CODE_PATCH'
    r['patch_generated']=bool(patches or any('diff' in (c.get('arguments') or {}) for c in calls if c['tool_name'] in ('validate_patch','run_tests')))

provider=api('/provider')
all_calls=provider['usage'].pop('calls')
history_program='''
import asyncio,json
from services.runtime import pool,query
async def main():
    await pool.open()
    rows=await query("SELECT r.id,r.incident_id,r.status, EXISTS(SELECT 1 FROM ai_patches p WHERE p.run_id=r.id AND p.origin='AI_GENERATED' AND p.artifact->>'candidate_verified'='true') candidate_verified FROM investigation_runs r WHERE r.mode='AI' AND EXISTS(SELECT 1 FROM agent_steps s WHERE s.incident_id=r.incident_id AND s.kind='Generating Patch' AND s.payload->>'run_id'=r.id::text) ORDER BY r.started_at")
    await pool.close()
    print(json.dumps(rows,default=str))
asyncio.run(main())
'''
history_scan=subprocess.run(['docker','compose','exec','-T','sentinel','python','-'],input=history_program,text=True,cwd=root,capture_output=True,check=True)
patch_history=json.loads(history_scan.stdout)
def call_totals(calls):
    successful=[c for c in calls if c['status']=='succeeded']
    return {'attempts':len(calls),'successful':len(successful),'failed_or_interrupted':len(calls)-len(successful),**{k:sum(c[k] for c in successful if c[k] is not None) for k in ('input_tokens','output_tokens','total_tokens')},'successful_calls_missing_usage':sum(c['total_tokens'] is None for c in successful),'estimated_cost':None}

current=[c for row in ledger for c in row['llm_calls']]
investigation_calls=[c for c in current if c['agent']!='Evaluator']
result={'generated_at':datetime.now(timezone.utc).isoformat(),'model':raw['model'],'scoring':'separate same-model judge; not independent human truth adjudication','aggregates':aggregates(results),'current_evaluation_llm_including_judge':call_totals(current),'current_ai_workflow_llm':call_totals(investigation_calls),'all_retained_llm':call_totals(all_calls),'all_retained_llm_by_role':{role:call_totals([c for c in all_calls if c['agent']==role]) for role in sorted({c['agent'] for c in all_calls})},'tool_calls':dict(Counter(row['mode'] for row in ledger for _ in row['tool_calls'])),'tool_calls_by_role':dict(Counter(c['agent'] for row in ledger for c in row['tool_calls'])),'results':results,'critic_verdicts':dict(Counter((r.get('critic') or {}).get('verdict','NO_CRITIC') for r in results if r['mode']=='AI')),'e2e_recovery_runs':[{'scenario':row['scenario'],'incident_id':row['incident_id'],'critic':((row['report'] or {}).get('critic') or {}).get('verdict'),'no_code_patch':(row['report'] or {}).get('diagnosis',{}).get('patch_decision')=='NO_CODE_PATCH','before':row['measured_recovery']['before'],'after':row['measured_recovery']['after'],'not_an_ai_repair':True} for row in ledger if row.get('measured_recovery')],'historical_failures':['phase2-pilot.json: invalid final schema','phase2-pilot-v2.json: genuine generated diffs rejected for missing envelope newline','phase2-evaluation-pre-observer-fix.json: includes observer contamination, context exhaustion, console error duplicate and final schema migration interference'],'production_patch_applied':any(r.get('patch_applied') for r in results),'cost':'Unknown: operator did not supply prices'}
result['historical_failures'].append('phase2-evaluation-v2-invalid-sql-identity.json plus phase2-v2-drained-run.json: interrupted invalid comparison; duplicate normalized SQL identities and Critic schema failures retained')
result['all_retained_ai_patch_attempts']={'investigations':len(patch_history),'verified':sum(r['candidate_verified'] for r in patch_history),'records':patch_history,'rate':sum(r['candidate_verified'] for r in patch_history)/len(patch_history) if patch_history else None}
result['workflow_completed']=dict(Counter(r['mode'] for r in results if r.get('run_status')=='completed'))
result['critic_false_verifications']=[{'scenario':r['scenario'],'incident_id':r['incident_id'],'judgment':r['judgment']} for r in results if r['mode']=='AI' and (r.get('critic') or {}).get('verdict')=='VERIFIED' and not r.get('judgment',{}).get('root_cause_correct')]
result['investigator_tool_calls']={mode:sum(1 for row in ledger if row['mode']==mode for call in row['tool_calls'] if call['agent'] in ('Investigator','RuleBasedInvestigator')) for mode in ('AI','RULE_BASED')}
(root/'docs/phase2-llm-call-ledger.json').write_text(json.dumps(all_calls,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'docs/phase2-delivery.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'docs/phase2-run-ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')

def verdict(row):
    if not row: return '缺失'
    return ('正确' if row.get('judgment',{}).get('root_cause_correct') else '错误/失败')
def fmt(value): return 'Unknown' if value is None else f'{value:.2f}'
def percent(value): return 'N/A' if value is None else f'{value*100:.1f}%'
ai=result['aggregates']['AI'];rules=result['aggregates']['RULE_BASED'];tokens=result['current_ai_workflow_llm']
lines=['# Project Sentinel 第二阶段实测评估','',f"生成时间：{result['generated_at']}。真实模型：`{raw['model']}`。",'',
'正式结果来自冻结的 V3 代码（`phase2-v3-manifest.json`）和真实容器，每个场景每种模式各一次。不是统计意义上的稳定准确率。Evaluator 是同一个模型的独立会话，评分存在波动；可用原始证据逐条复核。',
'', '## 逐场景结果','', '| 场景 | AI 根因评分 | AI 服务 | 规则评分 | Critic | AI 工具数 | AI 耗时秒 | 工作流 |','|---|---|---|---|---|---:|---:|---|']
for scenario in dict.fromkeys(r['scenario'] for r in results):
    a=next((r for r in results if r['scenario']==scenario and r['mode']=='AI'),{})
    b=next((r for r in results if r['scenario']==scenario and r['mode']=='RULE_BASED'),{})
    lines.append(f"| {scenario} | {verdict(a)} | {(a.get('diagnosis') or {}).get('affected_service','—')} | {verdict(b)} | {(a.get('critic') or {}).get('verdict','未完成')} | {a.get('tool_calls',0)} | {fmt(a.get('duration_seconds'))} | {a.get('run_status','runner_failed')} |")
lines+=['','## 可核查的 15 项交付结果','',
f"1. **Model**：`{raw['model']}`，真实 OpenAI-compatible API；密钥从本机 `.env` 动态读取。",
f"2. **LLM 调用**：本轮调查工作流 {tokens['attempts']} 次；含独立 Evaluator {len(current)} 次。所有保留轮次及 ProviderCheck 共 {len(all_calls)} 次（失败尝试计入）。",
f"3. **Tool Calls**：本轮 AI 全工作流 {result['tool_calls'].get('AI',0)} 次，规则 {result['tool_calls'].get('RULE_BASED',0)} 次；其中 Investigator 自主工具 {result['investigator_tool_calls']['AI']} 次。RecoveryObserver 与 Critic 的额外调用单独保留，不冒充 Investigator 决策。",
'4. **八场景**：见上表；完整根因、ground truth、证据 IDs、耗时、失败和 Patch 字段保存在 `phase2-delivery.json`。',
f"5. **Root Cause Accuracy**：AI {ai['root_cause_correct']}/{ai['scenarios']} = {percent(ai['root_cause_accuracy'])}；服务定位 {percent(ai['service_accuracy'])}。已验证提案即使后续 Critic 失败仍可独立评分，工作流失败保持失败。",
f"6. **Rule baseline**：{rules['root_cause_correct']}/{rules['scenarios']} = {percent(rules['root_cause_accuracy'])}；服务定位 {percent(rules['service_accuracy'])}。两者共用真实观测层，规则不读取真值。",
f"7. **AI Patch Success Rate**：本轮 {percent(ai['patch_success_rate'])}，分母 {ai['patch_denominator']} 个需要/实际尝试代码 Patch 的调查。NO_CODE_PATCH 不进入分母。无效 diff 与测试失败保留；历史 pilot 单独披露，不与正式轮混算。正式 Apply：{result['production_patch_applied']}，需要用户确认。",
'8. **测试**：29 项控制/协议/边界/回归测试通过。AI pricing 候选另执行 9 项不可变合同测试和 20 次基线 + 20 次候选真实 HTTP 重放，并有健康请求对照。失败基线用于证明原问题复现，不计为测试系统失败。',
f"9. **真实 E2E**：本轮 {len(result['e2e_recovery_runs'])} 个 NO_CODE_PATCH 调查包含服务端采集的恢复前后观测；数据库、下游调用与 Redis/Kafka 三类结果见下表。恢复由实验控制端执行，不能算 AI 修复。代码类另有 sandbox 验证。",
f"10. **Critic**：{json.dumps(result['critic_verdicts'],ensure_ascii=False)}。独立会话和结构化提交，不保证每次 VERIFIED。",
f"11. **Tokens**：本轮调查工作流 input={tokens['input_tokens']:,}, output={tokens['output_tokens']:,}, total={tokens['total_tokens']:,}；历史成功调用已返回用量累计={result['all_retained_llm']['total_tokens']:,}。认证失败没有返回 usage，不假设为零。均为 Provider 数据；费用 Unknown。",
'12. **Ground Truth Leakage**：未发现直接 capability/import/source/SQL 路径。只有终态 Evaluator 才读取注册表；工具无任意 shell/SQL/文件能力。这不是经过证明的 OS 级隔离。',
'13. **Mock / Hardcode**：未发现替代 AI 调查或遥测的 Mock。存在明确标记的种子商品、故障真值、规则 baseline 和协议错误测试服务；它们不计为 AI 成功。关键词和密钥扫描见 `hostile-audit.md`、`phase2-audit.json`。',
'14. **未完成**：通用仓库 Patch、多服务隔离重放、正式生产发布、RBAC/HA、精确断点恢复、跨模型/多轮随机评估、完整电商交易语义。',
'15. **最严重的三个限制**：①源码与修复覆盖面很窄，仅 pricing 可修改；②沙箱与 agent/evaluator 是受限能力隔离，非完整 OS/多服务安全边界；③单次小样本且同模型裁判，缺少独立人工标注、多次随机实验与生产工作流可靠性。',
'','## 比较口径','',
f"AI 平均全工作流工具数 {fmt(ai['average_tool_calls'])}，平均耗时 {fmt(ai['average_duration_seconds'])} 秒，证据质量评分 {fmt(ai['evidence_quality'])}/2。规则平均工具数 {fmt(rules['average_tool_calls'])}，平均耗时 {fmt(rules['average_duration_seconds'])} 秒，证据质量 {fmt(rules['evidence_quality'])}/2。AI 耗时包含恢复等待与 Critic，不能当成纯模型推理耗时。",'',
'## 三类恢复 E2E 与实测窗口','', '| 场景 | Incident | Critic | Before/After 来源 |','|---|---|---|---|']
for row in result['e2e_recovery_runs']:
    lines.append(f"| {row['scenario']} | {row['incident_id']} | {row['critic']} | Measured；HTTP/Pool/SQL/Redis/Kafka，operator recovery |")
lines+=['','| 场景 | 观测对象 | Error % 前 → 后 | P95 ms 前 → 后 | 其他实测 |','|---|---|---|---|---|']
for row in result['e2e_recovery_runs']:
    source=next(r for r in results if r['scenario']==row['scenario'] and r['mode']=='AI')
    service=source['expected_service']
    windows={w:next((h for h in row[w]['http'] if h['service']==service),{}) for w in ('before','after')}
    error=' → '.join(fmt(float(windows[w]['error_pct'])) if 'error_pct' in windows[w] else 'N/A' for w in ('before','after'))
    latency=' → '.join(fmt(windows[w].get('p95_ms')) for w in ('before','after'))
    lag=' → '.join(str(sum(p['lag'] for p in row[w]['kafka_lag'])) for w in ('before','after'))
    ttl=' → '.join(str(row[w].get('redis',{}).get('catalog_ttl','Unknown')) for w in ('before','after'))
    lines.append(f"| {row['scenario']} | {service} | {error} | {latency} | Kafka lag {lag}; catalog TTL {ttl} |")
lines+=['','所有恢复快照都有时间和 Evidence ID。数据库 Pool 与 Redis 累计量需要看差分；Kafka 用真实 committed/end offsets。20 秒 HTTP 窗口包含少量 pool-stats 诊断请求，不能直接视为纯业务压测。','','## 失败保留与版本','']
lines += ['- '+s for s in result['historical_failures']]
lines += ['- `phase2-v3-code-preflight.json`：冻结评估前真实代码闭环预检，9 tests / HTTP replay / Critic VERIFIED；单独保存，不计入八场景分母。',
'', '第一轮控制台编码异常产生的重复行仍存在原始文件。V1/V2 观测器缺陷与开发迁移干扰让它们不适合作为公平基线；没有删除它们，也没有把它们的后续修复描述为模型原先就成功。正式 V3 不因错误答案重新选择最佳结果。',
'','## 重现','', '```powershell','docker compose up -d --build','docker compose exec -T sentinel python -m pytest -q -p no:cacheprovider tests/test_controls.py tests/test_agent_phase2.py','python scripts/evaluate_phase2.py --controlled-recovery --output docs/my-evaluation.json','```','',
'先执行测试，再开始冻结评估。评估期间不要迁移/重启；不在多个终端同时运行故障实验。调查结束后再引入真值。',
'', '详细账本：`phase2-run-ledger.json`、`phase2-llm-call-ledger.json`。SSE 实测：`sse-ai-verification.json`。']
lines += ['',f"历史全部真实 AI Patch 尝试（按开始 FixAgent 的调查计，包括失败）为 {result['all_retained_ai_patch_attempts']['verified']}/{len(patch_history)} = {percent(result['all_retained_ai_patch_attempts']['rate'])}。详细 run IDs 在交付 JSON 中。这与冻结八场景的 Patch 成功率分别报告。"]
lines += ['', '## 错判与 Critic 误放行', '']
for row in results:
    if not row.get('judgment',{}).get('root_cause_correct'):
        lines += ['### '+row['mode']+' / '+row['scenario'],'', '**实际提交的根因**：'+(row.get('diagnosis') or {}).get('root_cause','未产生有效提案'),'', '**事后评分原因**：'+row.get('judgment',{}).get('explanation',str(row.get('error'))),'', '**Critic**：'+(row.get('critic') or {}).get('verdict','N/A 或未完成')+'；完整分析与证据保留在账本。','']
lines += ['基线 retry_storm 的严格评分存在人工复核价值：规则已经识别重试放大和正确服务，裁判因文字未说明“立即重试、无退避”而判错。本报告保留原始裁判结果，没有把这个分数描述为无争议的客观事实，也没有改写规则答案后重跑。']
lines += [f"共 {len(result['critic_false_verifications'])} 次 Critic VERIFIED 被事后根因评分判错。独立角色会话不等于独立可靠性，不能把 VERIFIED 当成事实。当前手动评估的 Incident 初始快照以 HTTP 为主；数据库、缓存和队列异常需由真实工具发现。AI 未充分利用这些信号，HTTP 正常时的漏诊是当前明确弱点。"]
(root/'docs/evaluation.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k in ('model','aggregates','current_evaluation_llm_including_judge','current_ai_workflow_llm','all_retained_llm','tool_calls','critic_verdicts','production_patch_applied')},ensure_ascii=True,indent=2))
