"""Publish a factual delivery document from experiment artifacts, including failures."""
import json
from pathlib import Path
from datetime import datetime,timezone
from phase3_dataset import dataset_path

ROOT=Path(__file__).resolve().parents[1]
def load(path): return json.loads((ROOT/path).read_text(encoding='utf-8'))
def number(v): return 'Unknown' if v is None else f'{float(v):,.2f}'.rstrip('0').rstrip('.')
def pct(v): return 'Unknown' if v is None else f'{100*v:.1f}%'
def change(new,old): return None if new is None or old in (None,0) else (old-new)/old


def main():
    report=load('evaluation/comparison.json');versions={v['key']:v for v in report['versions']}
    audit=load('evaluation/audit.json');tests=load('evaluation/tests-final.json')
    runtime_audit=load('evaluation/runtime-audit.json');integrity=load('evaluation/artifact-validation.json')
    resume=load('evaluation/resume-post-evaluation.json')
    validity=load('evaluation/fault-validity.json')
    deployment=load('evaluation/delivery-runtime.json');ui=load('evaluation/ui-validation.json');worker=load('evaluation/fault-worker-live-smoke.json')
    headings=[v['label'] for v in report['versions']]
    lines=['# Project Sentinel 第三阶段实测交付','',f"生成时间：{datetime.now(timezone.utc).isoformat()}。模型：deepseek-chat。按预先声明的有效性规则使用每场景每版本首次有效试验，保留所有失败和失效注入记录。",'',
        '**V1 原始结果不变**：Pure LLM 根因 5/8=62.5%，服务定位 62.5%；Rule 根因 7/8=87.5%，服务定位 100%。原始阶段共 78 次调查工作流模型调用、16 次评分调用，AI 工作流工具 261 次，其中 Investigator 182 次；input=1,375,940、output=41,707、total=1,417,647，Cost=Unknown。AI Patch 正式 1/1、含历史 2/3。Critic 4 VERIFIED / 4 PARTIALLY_VERIFIED，Kafka 有 1 次错误 VERIFIED。', '',
        '这些原始文件、评分器、故障定义和旧文档保存在只读基线及 archive.zip 中；SHA-256 校验用于发现修改，不宣称具备管理员不可篡改的 WORM 存储。', '',
        '## 四组完整比较','',report['dataset_note'],'',
        '主表统一使用**调查工作流**口径，不含 Evaluator。因此 V1 此表 tokens 为 1,261,196；上面的 1,417,647 包括两组共 16 次评分调用，两者不可混算。耗时包含操作员恢复等待和 Critic，不是纯 LLM 推理延迟。提前失败会降低用量和耗时；若准确率或完成率下降，不能把 Token 下降宣称为优化成功。', '',
        '| 指标 | '+' | '.join(headings)+' |','|---|'+'---:|'*4]
    fields=[('Root Cause Accuracy','root_accuracy',pct),('Service Localization','service_accuracy',pct),('完成工作流 / 8','workflow_completed',number),
            ('LLM Calls','llm_calls',number),('Tool Calls','tool_calls',number),('Useful Tool Rate（启发式）','useful_rate',pct),
            ('Input Tokens','input_tokens',number),('Output Tokens','output_tokens',number),('Total Tokens','total_tokens',number),
            ('平均工作流耗时 / 秒','average_duration',number),('Critic False Accept','critic_false_accept',number),('Patch Success','patch_success',pct)]
    for title,key,fmt in fields: lines.append('| '+title+' | '+' | '.join(fmt(v['metrics'][key]) for v in report['versions'])+' |')
    lines+=['','Useful Tool Rate 使用相同 role/tool/arguments 的重复查询启发式回溯计算。它把某些有价值的时间差分查询也算作重复，且首次查询不一定相关；不能当成人工语义有效率。Rule 未运行 Critic，其 0 次误放行不表示验证器更可靠。', '',
            'VERIFIED 覆盖也必须同时看：'+'；'.join(v['label']+f" 共 {v['metrics']['critic_verified_count']} 次 VERIFIED，其中根因正确 {v['metrics']['correct_and_verified']} 次" for v in report['versions'][1:])+'。减少误放行可能伴随更多正确诊断停留在 PARTIALLY_VERIFIED，不能仅凭 false accept=0 宣称验证能力全面提高。', '',
            '## 八场景矩阵','', '| 场景 | Rule 根因/定位 | V1 根因/定位 | V2 根因/定位 | V3 根因/定位 |','|---|---|---|---|---|']
    for scenario in report['scenarios']:
        values=[]
        for v in report['versions']:
            row=next((r for r in v['results'] if r['scenario']==scenario),None)
            values.append(('正确' if row['correct'] else '错误')+'/'+('正确' if row['service_correct'] else '错误') if row else '未运行')
        lines.append('| '+scenario+' | '+' | '.join(values)+' |')
    lines+=['','## 注入有效性与原始轮次保留','',
            '初次连接池故障仅绕过缓存，后台占用连接的任务没有执行。修复实验环境后只补测这一条；其余实际 Agent 错误仍进入分母。新增文件为 `v2-hybrid-validated.json` 和 `v3-context-optimized-validated.json`，原始 `v2-hybrid.json` / `v3-context-optimized.json` 不覆盖。', '',
            '| 版本 | 初始记录根因 / 定位 | 有效试验根因 / 定位 | 失效注入 Incident |','|---|---|---|---|']
    for v in report['versions'][2:]:
        selection=v.get('selection_policy') or {}
        lines.append(f"| {v['label']} | {selection.get('initial_root_correct','Unknown')}/8 / {selection.get('initial_service_correct','Unknown')}/8 | {pct(v['metrics']['root_accuracy'])} / {pct(v['metrics']['service_accuracy'])} | {selection.get('excluded_incident_id','无已验证补测')} |")
    a=versions['v1']['metrics'];b=versions['v2']['metrics'];c=versions['v3']['metrics']
    lines+=['', '**实验结论**：V2 在缓存与 Kafka 上改善了 V1 的判断，Retry Storm 和下游超时仍错误。V3 的准确率与工作流完成率明显下降；压缩与强制收敛的当前实现未达到质量目标，Token 减少还混有提前失败效应。默认新调查改为 V2，V3 保留为显式实验模式，没有静默回退。', '',
        '补测期间评分接口曾返回 HTTP 409：保留同一 V2 Incident，仅重试评分，没有重跑调查。两次评分模型调用都计入账本。中止前未保存的外层健康窗口保持 Unknown，故障中及恢复后使用同一 run 已持久化的 RecoveryObserver 实测；详见补测文件的 provenance_note。', '',
        '实验结束后的运维修复仅包括 API 默认模式选择，以及后台故障任务在 RedisError 后等待一秒继续。后者修复已观察到的 Redis 启动 DNS 失败使任务永久退出的问题，不改变故障 SQL、并发数、持续时间、评分器或业务处理器。精确实验源码另存 `evaluation/frozen-framework.zip`；当前代码差异以字节/AST 限定校验。']
    dev=report['development_usage']
    lines += ['', '## 中止轮次和开发消耗（保留，不计入正式准确率）','',
        '第一次 V2 在慢查询场景反复把解释文字拼入 Evidence ID，根因提交遭拒并耗尽上下文。修复字段 schema 和错误提示后，完整重启八场景评估；没有更改故障、评分器或按场景编写答案。该轮及在途的第二个调查保存在 `evaluation/interruptions.json` 引用的原始文件中。此前三次真实重启预检也全部保留。', '',
        f"这些额外记录按模型调用 ID 去重后：{dev['llm_calls']} 次调用，已知 {number(dev['known_tokens'])} tokens，{dev['missing_usage_calls']} 次缺少 usage，缺失量为 Unknown，费用 Unknown。该数不含不归属调查 run 的连接探针。正式主表未把这些消耗计成成功运行，也未把它们删除。", '',
        '| 保留记录 | 快照调用数 | 已知 Tokens（快照之间可能重叠） |','|---|---:|---:|']
    for artifact in dev['artifacts']:
        lines.append(f"| {artifact['file']} | {artifact['calls_in_snapshot']} | {number(artifact['known_tokens'])} |")
    def improvement(key):
        old=next(r for r in versions['v1']['results'] if r['scenario']==key)
        return key+'：'+'; '.join(v['label']+': '+('根因正确' if (r:=next((r for r in v['results'] if r['scenario']==key),{})).get('correct') else '根因错误/未完成')+' / '+('定位正确' if r.get('service_correct') else '定位错误/未完成') for v in report['versions'][1:])
    lines+=['','## 25 项交付核对','',
        '1. **V1 原始结果**：见首段与只读基线；包括错误判定、Kafka 误放行和历史 Patch 失败。',
        f"2. **V2 Hybrid**：根因 {pct(b['root_accuracy'])}，定位 {pct(b['service_accuracy'])}，有效集合 `evaluation/results/v2-hybrid-validated.json`；初始原件 `v2-hybrid.json` 保留。",
        f"3. **V3 Context Optimized**：根因 {pct(c['root_accuracy'])}，定位 {pct(c['service_accuracy'])}，有效集合 `evaluation/results/v3-context-optimized-validated.json`；初始原件 `v3-context-optimized.json` 保留。",
        '4. **Rule Baseline**：保持原始 7/8、定位 8/8，没有重新评判 retry_storm 的争议分数。',
        '5. **四者对比**：见上表，分母与 token 口径一致。',
        '6. **每场景结果**：见矩阵、下方逐项预测与评分理由以及 Dashboard 可点击单元格。',
        '7. **Redis / Kafka / Retry**：'+ '\n   '.join(improvement(s) for s in ('cache_miss','consumer_lag','retry_storm')),
        f"8. **根因变化**：V1 {pct(a['root_accuracy'])} → V2 {pct(b['root_accuracy'])} → V3 {pct(c['root_accuracy'])}。",
        f"9. **服务定位变化**：V1 {pct(a['service_accuracy'])} → V2 {pct(b['service_accuracy'])} → V3 {pct(c['service_accuracy'])}。",
        f"10. **工作流 Token**：{number(a['total_tokens'])} → {number(b['total_tokens'])} → {number(c['total_tokens'])}。Provider reported，失败/中断未返回 usage 的部分仍为未知。",
        f"11. **Token 节省**：V2 相对 V1 {pct(change(b['total_tokens'],a['total_tokens']))}；V3 相对 V1 {pct(change(c['total_tokens'],a['total_tokens']))}；V3 相对 V2 {pct(change(c['total_tokens'],b['total_tokens']))}。负数表示增加。",
        f"12. **工具调用**：{number(a['tool_calls'])} → {number(b['tool_calls'])} → {number(c['tool_calls'])}，包含 Triage / RecoveryObserver / Critic 等角色，逐次账本可核查。",
        f"13. **Useful Tool Rate**：{pct(a['useful_rate'])} → {pct(b['useful_rate'])} → {pct(c['useful_rate'])}，仅作重复查询代理指标。",
        f"14. **平均耗时**：{number(a['average_duration'])} → {number(b['average_duration'])} → {number(c['average_duration'])} 秒。",
        f"15. **Critic 误放行**：{number(a['critic_false_accept'])} → {number(b['critic_false_accept'])} → {number(c['critic_false_accept'])}，同时保留最终 verdict 和 deterministic/LLM disagreement，不能用全部拒绝来声称高可靠性。",
        f"16. **Patch Success**：V1 {pct(a['patch_success'])}（分母 {a['patch_denominator']}），V2 {pct(b['patch_success'])}（分母 {b['patch_denominator']}），V3 {pct(c['patch_success'])}（分母 {c['patch_denominator']}）。NO_CODE_PATCH 不进入分母，未执行 Apply。",
        '17. **新增 Service Patch**：没有新增安全可执行的服务范围。仍为 order-service 中的 pricing 函数；payment、inventory 和通用 order handler Patch **未完成**。现有业务与故障控制耦合，未为扩大范围而开放整个 app.py 或放宽执行沙箱。已增加风险分类与拒绝边界。',
        '18. **NO_CODE_PATCH**：生成带不确定性和操作建议的 Remediation Plan，实际恢复由实验控制端停止故障，并用服务端观测 Before/After；不是 AI 修复。逐运行成功/失败见下方 E2E。',
        f"19. **Checkpoint Resume**：真实 PostgreSQL/Redis 测试证明已提交工具可复用。最终 {resume['mode']} 容器重启检验 passed={resume['passed']}，same_run={resume.get('same_run')}，original_evidence_preserved={resume.get('original_evidence_preserved')}，终态={resume.get('final_checkpoint',{}).get('phase')}，Incident={resume['incident_id']}。这是健康工作负载上的恢复实验，不计入故障准确率；此前 V3 重启后预算失败全部保留，不能用本次结果覆盖它们。详见 `evaluation/resume-post-evaluation.json`。",
        f"20. **Ground Truth Audit**：静态 capability 发现 {len(audit['capability_findings'])} 项；运行时证据真值字段命中 {len(runtime_audit['truth_field_evidence_matches'])} 项，数据库当前密钥命中 {sum(runtime_audit['secret_rows_by_table'].values())} 行，日志密钥命中 {runtime_audit['sentinel_logs_secret_match']}。真值仅在控制、事后评分和操作员 UI 路径。非 OS 级隔离证明。",
        '21. **Scenario Hardcode Audit**：Hybrid/Planner/Context/Verifier 不按 scenario_id 分支；业务故障注册表和原评分代码哈希未变。拓扑中的配置边明确标记为配置，并非观测结果。',
        '22. **Mock Audit**：协议错误服务和合成边界测试不计入准确率；正式实验使用实时容器、真实故障、真实工具及模型，Replay 清晰标记 RECORDED RUN。',
        f"23. **自动化测试**：{tests['passed']} passed / {tests['failed']} failed，{tests['seconds']} 秒；原有 29 项保留，新增 {tests['passed']+tests['failed']-29} 项。包含后台故障任务短暂 Redis 异常后的恢复边界测试，它不计入准确率。旧测试失败与依赖未就绪中止记录在开发记录中。Patch 合同测试与 HTTP replay 另列在候选 artifact，不混入此数量。",
        '24. **至少五个 Live E2E**：Redis、Kafka、Retry，加固定随机种子选出的数据库场景和代码场景。两组都实际执行全部八场景；下面区分“已执行”和“工作流闭环通过”，不把根因错误或执行失败伪装成功。',
        '25. **五个最大限制**：①V3 质量目标未达成，输出协议和预算收敛仍导致多次失败；②通用多服务 Patch 尚未完成，沙箱仅为 pricing HTTP harness + live inventory；③同模型 Investigator/Critic/Judge 且每场景仅一次，确定性门禁不能证明语义因果；④真值隔离是能力边界，调查/评分仍共享进程与数据库，尚无生产多租户隔离；⑤恢复是单进程阶段/工具游标恢复，远端 LLM 和 Patch 操作不具备端到端 exactly-once，V3 重启预检存在失败。',
        '', '## 真实 E2E 及 Critic 分布','']
    for version,file in (('v2','evaluation/results/v2-hybrid.json'),('v3','evaluation/results/v3-context-optimized.json')):
        source=json.loads(dataset_path(version).read_text(encoding='utf-8'));selected=source['e2e_selection']['scenarios']
        lines += [f"### {versions[version]['label']}（数据库抽样 seed={source['e2e_selection']['seed']}）",'',
            '| 场景 | Incident | 工作流完成 | 根因评分 | NO_CODE_PATCH / sandbox | 恢复前后观测 |','|---|---|---|---|---|---|']
        for r in source['results']:
            if r['scenario'] not in selected: continue
            d=r.get('diagnosis') or {};measured=r.get('measured_recovery')
            lines.append(f"| {r['scenario']} | {r['incident_id']} | {r.get('workflow_completed',False)} | {r.get('judgment',{}).get('root_cause_correct',False)} | {d.get('patch_decision','无有效诊断')} | {'Observer before/after' if measured else 'Sandbox replay' if r.get('fault_replay_passed') else '仅实验外层测量/未闭环'} |")
        verdicts={}
        for r in source['results']:
            v=(r.get('critic') or {}).get('verdict','NO_CRITIC');verdicts[v]=verdicts.get(v,0)+1
        lines+=['', '最终 Critic 分布：`'+json.dumps(verdicts)+'`。','']
        lines+=['外层真实观测（每格为故障前 → 故障中 → 控制端恢复后；这些窗口不计为 AI 修复）：','',
                '| 场景 | Gateway 错误率 % | Gateway P95 ms | Kafka lag |','|---|---|---|---|']
        for r in source['results']:
            windows=[r.get('measured',{}).get(k,{}) for k in ('before','fault_active','after')]
            http=[next((h for h in w.get('http',[]) if h['service']=='gateway'),{}) for w in windows]
            lag=[sum(x['lag'] for x in w['kafka_lag']) if w.get('kafka_lag') and all(x.get('lag') is not None for x in w['kafka_lag']) else None for w in windows]
            series=[' → '.join(number(h.get(k)) for h in http) for k in ('error_pct','p95_ms')]
            lines.append('| '+r['scenario']+' | '+' | '.join(series+[' → '.join(number(x) for x in lag)])+' |')
        lines.append('')
    lines+=['## 新实验逐项预测与评分理由','']
    for version in ('v2','v3'):
        for r in versions[version]['results']:
            lines += ['### '+versions[version]['label']+' / '+r['scenario'],'',
                '**预测服务**：'+str(r.get('predicted_service')),'', '**预测根因**：'+str(r.get('predicted_root_cause')),'',
                '**原始评分 / 失败说明**：'+r['failure_analysis'],'']
    lines+=['## 记录完整性','',
        f"{len(integrity['checks'])} 项记录检查，完整性通过={integrity['passed_integrity']}。检查了 V2/V3 同一实验源码与实际容器哈希、16 个独立 run、工具与 Evidence 外键、模型名称与 usage 算术、终态后的评分调用、未自动 Apply 以及服务端恢复观测。实验后仅有明确记录的运维修复。故障有效性证据另见 `evaluation/fault-validity.json`，不是依据模型答对与否判定注入成功。完整性通过不等于所有根因或工作流通过。", '',
        '## 最终运行状态与 UI 验证','',
        f"交付检查通过={deployment['passed']}；{len(deployment['containers'])} 个 Compose 容器运行，{len(deployment['runtime_source_sha256'])} 个容器内 Python/Web 文件与当前交付源码一致。活跃故障={deployment['active_faults']}，流量开启={deployment['traffic_enabled']}，评估锁存在={deployment['evaluation_lock_exists']}。详细时点和真实指标见 `evaluation/delivery-runtime.json`。", '',
        f"后台故障执行器修复后的真实占满/停止恢复验证通过={worker['passed']}，该检查没有调用模型，不进入准确率。浏览器验证通过={ui['passed']}：四组实测、图表切换、场景证据、Critic、失败原因、播放/暂停/末尾跳转均检查；最终浏览器无 console warning/error。见 `evaluation/ui-validation.json`。", '',
        '## 重现与审计','',
        '```powershell','docker compose up -d --build','docker compose run --rm --no-deps sentinel python -m pytest -q -p no:cacheprovider tests/test_controls.py tests/test_agent_phase2.py tests/test_hybrid.py tests/test_worker_recovery.py',
        '# 正式输出不可覆盖；另开有明确标记的实验文件才能做新实验。','python scripts/report_phase3.py','python scripts/audit_phase3.py','python scripts/audit_runtime_phase3.py','python scripts/verify_phase3_artifacts.py','python scripts/deliver_phase3.py','```','',
        '不要在冻结实验期间执行迁移、测试或重启。`evaluate_phase3.py` 会拒绝覆盖已有正式文件；只有调查终态后 Evaluator 才读取真值。V1 冻结 artifact 没有重新生成。', '',
        'UI：http://localhost:18082/evaluation.html。场景单元格包含真值、预测、评分理由、证据、工具时间线、Provider 分角色用量，以及有明确录制标记的回放。']
    text='\n'.join(lines)+'\n'
    (ROOT/'docs/evaluation.md').write_text(text,encoding='utf-8')
    (ROOT/'docs/phase3-delivery.md').write_text(text,encoding='utf-8')
    print(json.dumps({'all_formal_runs_complete':report['all_completed'],'report':'docs/phase3-delivery.md'}))


if __name__=='__main__': main()
