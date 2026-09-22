# Project Sentinel 第三阶段实测交付

生成时间：2026-09-21T12:02:48.969790+00:00。模型：deepseek-chat。按预先声明的有效性规则使用每场景每版本首次有效试验，保留所有失败和失效注入记录。

**V1 原始结果不变**：Pure LLM 根因 5/8 (62.5%)，服务定位 5/8 (62.5%)；Rule 根因 7/8 (87.5%)，服务定位 100%。原始阶段共 78 次调查工作流模型调用、16 次评分调用，AI 工作流工具 261 次，其中 Investigator 182 次；input=1,375,940、output=41,707、total=1,417,647，Cost=Unknown。AI Patch 正式 1/1、含历史 2/3。Critic 4 VERIFIED / 4 PARTIALLY_VERIFIED，Kafka 有 1 次错误 VERIFIED。

这些原始文件、评分器、故障定义和旧文档保存在只读基线及 archive.zip 中；SHA-256 校验用于发现修改，不宣称具备管理员不可篡改的 WORM 存储。

## 四组完整比较

连接池初次注入未生效，经同镜像重启前后测量证明并各补测一次；主表采用首次有效试验，原始两组结果及其他所有错误均保留。

主表统一使用**调查工作流**口径，不含 Evaluator。因此 V1 此表 tokens 为 1,261,196；上面的 1,417,647 包括两组共 16 次评分调用，两者不可混算。耗时包含操作员恢复等待和 Critic，不是纯 LLM 推理延迟。提前失败会降低用量和耗时；若准确率或完成率下降，不能把 Token 下降宣称为优化成功。

| 指标 | Rule Baseline | Pure LLM V1 | Hybrid V2 | Context Optimized V3 |
|---|---:|---:|---:|---:|
| Root Cause Accuracy | 7/8 (87.5%) | 5/8 (62.5%) | 6/8 (75.0%) | 1/8 (12.5%) |
| Service Localization | 8/8 (100.0%) | 5/8 (62.5%) | 6/8 (75.0%) | 1/8 (12.5%) |
| 完成工作流 / 8 | 8 | 8 | 8 | 2 |
| LLM Calls | 0 | 78 | 80 | 77 |
| Tool Calls | 72 | 261 | 278 | 280 |
| Useful Tool Rate（启发式） | 8/8 (100.0%) | 84.7% | 78.8% | 66.4% |
| Input Tokens | 0 | 1,222,515 | 1,487,387 | 859,254 |
| Output Tokens | 0 | 38,681 | 44,255 | 37,126 |
| Total Tokens | 0 | 1,261,196 | 1,531,642 | 896,380 |
| 平均工作流耗时 / 秒 | 11.62 | 68.14 | 123.47 | 87.31 |
| Critic False Accept | 0 | 1 | 0 | 0 |
| Patch Success | 8/8 (100.0%) | 8/8 (100.0%) | 8/8 (100.0%) | Unknown |

Useful Tool Rate 使用相同 role/tool/arguments 的重复查询启发式回溯计算。它把某些有价值的时间差分查询也算作重复，且首次查询不一定相关；不能当成人工语义有效率。Rule 未运行 Critic，其 0 次误放行不表示验证器更可靠。

VERIFIED 覆盖也必须同时看：Pure LLM V1 共 4 次 VERIFIED，其中根因正确 3 次；Hybrid V2 共 2 次 VERIFIED，其中根因正确 2 次；Context Optimized V3 共 1 次 VERIFIED，其中根因正确 1 次。减少误放行可能伴随更多正确诊断停留在 PARTIALLY_VERIFIED，不能仅凭 false accept=0 宣称验证能力全面提高。

## 八场景矩阵

| 场景 | Rule 根因/定位 | V1 根因/定位 | V2 根因/定位 | V3 根因/定位 |
|---|---|---|---|---|
| slow_query | 正确/正确 | 正确/正确 | 正确/正确 | 正确/正确 |
| pool_exhaustion | 正确/正确 | 正确/正确 | 正确/正确 | 错误/错误 |
| n_plus_one | 正确/正确 | 正确/正确 | 正确/正确 | 错误/错误 |
| cache_miss | 正确/正确 | 错误/正确 | 正确/正确 | 错误/错误 |
| consumer_lag | 正确/正确 | 错误/错误 | 正确/正确 | 错误/错误 |
| downstream_timeout | 正确/正确 | 正确/错误 | 错误/错误 | 错误/错误 |
| retry_storm | 错误/正确 | 错误/错误 | 错误/错误 | 错误/错误 |
| code_exception | 正确/正确 | 正确/正确 | 正确/正确 | 错误/错误 |

## 注入有效性与原始轮次保留

初次连接池故障仅绕过缓存，后台占用连接的任务没有执行。修复实验环境后只补测这一条；其余实际 Agent 错误仍进入分母。新增文件为 `v2-hybrid-validated.json` 和 `v3-context-optimized-validated.json`，原始 `v2-hybrid.json` / `v3-context-optimized.json` 不覆盖。

| 版本 | 初始记录根因 / 定位 | 有效试验根因 / 定位 | 失效注入 Incident |
|---|---|---|---|
| Hybrid V2 | 5/8 / 5/8 | 6/8 (75.0%) / 6/8 (75.0%) | 9aaeab70-193e-43a3-b687-55b2ec65edf4 |
| Context Optimized V3 | 1/8 / 2/8 | 1/8 (12.5%) / 1/8 (12.5%) | 18795b50-71c1-4656-841b-bbd7de58c319 |

**实验结论**：V2 在缓存与 Kafka 上改善了 V1 的判断，Retry Storm 和下游超时仍错误。V3 的准确率与工作流完成率明显下降；压缩与强制收敛的当前实现未达到质量目标，Token 减少还混有提前失败效应。默认新调查改为 V2，V3 保留为显式实验模式，没有静默回退。

补测期间评分接口曾返回 HTTP 409：保留同一 V2 Incident，仅重试评分，没有重跑调查。两次评分模型调用都计入账本。中止前未保存的外层健康窗口保持 Unknown，故障中及恢复后使用同一 run 已持久化的 RecoveryObserver 实测；详见补测文件的 provenance_note。

实验结束后的运维修复仅包括 API 默认模式选择，以及后台故障任务在 RedisError 后等待一秒继续。后者修复已观察到的 Redis 启动 DNS 失败使任务永久退出的问题，不改变故障 SQL、并发数、持续时间、评分器或业务处理器。精确实验源码另存 `evaluation/frozen-framework.zip`；当前代码差异以字节/AST 限定校验。

## 中止轮次和开发消耗（保留，不计入正式准确率）

第一次 V2 在慢查询场景反复把解释文字拼入 Evidence ID，根因提交遭拒并耗尽上下文。修复字段 schema 和错误提示后，完整重启八场景评估；没有更改故障、评分器或按场景编写答案。该轮及在途的第二个调查保存在 `evaluation/interruptions.json` 引用的原始文件中。此前三次真实重启预检也全部保留。

这些额外记录按模型调用 ID 去重后：77 次调用，已知 1,029,561 tokens，2 次缺少 usage，缺失量为 Unknown，费用 Unknown。该数不含不归属调查 run 的连接探针。正式主表未把这些消耗计成成功运行，也未把它们删除。

| 保留记录 | 快照调用数 | 已知 Tokens（快照之间可能重叠） |
|---|---:|---:|
| evaluation/resume-final.json | 12 | 129,649 |
| evaluation/resume-live-after-loop-fix.json | 11 | 96,969 |
| evaluation/resume-live.json | 10 | 87,560 |
| evaluation/resume-post-evaluation.json | 12 | 193,872 |
| evaluation/resume-preflight-failure.json | 1 | 6,842 |
| evaluation/aborted-second-run.json | 1 | 7,865 |
| evaluation/results/v2-hybrid-interrupted-schema-loop.json | 12 | 248,958 |
| evaluation/results/v2-hybrid.json [invalid pool fixture only] | 7 | 118,662 |
| evaluation/results/v3-context-optimized.json [invalid pool fixture only] | 12 | 146,026 |

## 25 项交付核对

1. **V1 原始结果**：见首段与只读基线；包括错误判定、Kafka 误放行和历史 Patch 失败。
2. **V2 Hybrid**：根因 6/8 (75.0%)，定位 6/8 (75.0%)，有效集合 `evaluation/results/v2-hybrid-validated.json`；初始原件 `v2-hybrid.json` 保留。
3. **V3 Context Optimized**：根因 1/8 (12.5%)，定位 1/8 (12.5%)，有效集合 `evaluation/results/v3-context-optimized-validated.json`；初始原件 `v3-context-optimized.json` 保留。
4. **Rule Baseline**：保持原始 7/8、定位 8/8，没有重新评判 retry_storm 的争议分数。
5. **四者对比**：见上表，分母与 token 口径一致。
6. **每场景结果**：见矩阵、下方逐项预测与评分理由以及 Dashboard 可点击单元格。
7. **Redis / Kafka / Retry**：cache_miss：Pure LLM V1: 根因错误/未完成 / 定位正确; Hybrid V2: 根因正确 / 定位正确; Context Optimized V3: 根因错误/未完成 / 定位错误/未完成
   consumer_lag：Pure LLM V1: 根因错误/未完成 / 定位错误/未完成; Hybrid V2: 根因正确 / 定位正确; Context Optimized V3: 根因错误/未完成 / 定位错误/未完成
   retry_storm：Pure LLM V1: 根因错误/未完成 / 定位错误/未完成; Hybrid V2: 根因错误/未完成 / 定位错误/未完成; Context Optimized V3: 根因错误/未完成 / 定位错误/未完成
8. **根因变化**：V1 5/8 (62.5%) → V2 6/8 (75.0%) → V3 1/8 (12.5%)。
9. **服务定位变化**：V1 5/8 (62.5%) → V2 6/8 (75.0%) → V3 1/8 (12.5%)。
10. **工作流 Token**：1,261,196 → 1,531,642 → 896,380。Provider reported，失败/中断未返回 usage 的部分仍为未知。
11. **Token 节省**：V2 相对 V1 -21.4%；V3 相对 V1 28.9%；V3 相对 V2 41.5%。负数表示增加。
12. **工具调用**：261 → 278 → 280，包含 Triage / RecoveryObserver / Critic 等角色，逐次账本可核查。
13. **Useful Tool Rate**：84.7% → 78.8% → 66.4%，仅作重复查询代理指标。
14. **平均耗时**：68.14 → 123.47 → 87.31 秒。
15. **Critic 误放行**：1 → 0 → 0，同时保留最终 verdict 和 deterministic/LLM disagreement，不能用全部拒绝来声称高可靠性。
16. **Patch Success**：V1 8/8 (100.0%)（分母 1），V2 8/8 (100.0%)（分母 1），V3 Unknown（分母 0）。NO_CODE_PATCH 不进入分母，未执行 Apply。
17. **新增 Service Patch**：没有新增安全可执行的服务范围。仍为 order-service 中的 pricing 函数；payment、inventory 和通用 order handler Patch **未完成**。现有业务与故障控制耦合，未为扩大范围而开放整个 app.py 或放宽执行沙箱。已增加风险分类与拒绝边界。
18. **NO_CODE_PATCH**：生成带不确定性和操作建议的 Remediation Plan，实际恢复由实验控制端停止故障，并用服务端观测 Before/After；不是 AI 修复。逐运行成功/失败见下方 E2E。
19. **Checkpoint Resume**：真实 PostgreSQL/Redis 测试证明已提交工具可复用。最终 HYBRID_V2 容器重启检验 passed=True，same_run=True，original_evidence_preserved=True，终态=COMPLETED，Incident=ca097c01-02c6-4469-be32-e9207bbcb58c。这是健康工作负载上的恢复实验，不计入故障准确率；此前 V3 重启后预算失败全部保留，不能用本次结果覆盖它们。详见 `evaluation/resume-post-evaluation.json`。
20. **Ground Truth Audit**：静态 capability 发现 0 项；运行时证据真值字段命中 0 项，数据库当前密钥命中 0 行，日志密钥命中 False。真值仅在控制、事后评分和操作员 UI 路径。非 OS 级隔离证明。
21. **Scenario Hardcode Audit**：Hybrid/Planner/Context/Verifier 不按 scenario_id 分支；业务故障注册表和原评分代码哈希未变。拓扑中的配置边明确标记为配置，并非观测结果。
22. **Mock Audit**：协议错误服务和合成边界测试不计入准确率；正式实验使用实时容器、真实故障、真实工具及模型，Replay 清晰标记 RECORDED RUN。
23. **自动化测试**：49 passed / 0 failed，6.6 秒；原有 29 项保留，新增 20 项。包含后台故障任务短暂 Redis 异常后的恢复边界测试，它不计入准确率。旧测试失败与依赖未就绪中止记录在开发记录中。Patch 合同测试与 HTTP replay 另列在候选 artifact，不混入此数量。
24. **至少五个 Live E2E**：Redis、Kafka、Retry，加固定随机种子选出的数据库场景和代码场景。两组都实际执行全部八场景；下面区分“已执行”和“工作流闭环通过”，不把根因错误或执行失败伪装成功。
25. **五个最大限制**：①V3 质量目标未达成，输出协议和预算收敛仍导致多次失败；②通用多服务 Patch 尚未完成，沙箱仅为 pricing HTTP harness + live inventory；③同模型 Investigator/Critic/Judge 且每场景仅一次，确定性门禁不能证明语义因果；④真值隔离是能力边界，调查/评分仍共享进程与数据库，尚无生产多租户隔离；⑤恢复是单进程阶段/工具游标恢复，远端 LLM 和 Patch 操作不具备端到端 exactly-once，V3 重启预检存在失败。

## 真实 E2E 及 Critic 分布

### Hybrid V2（数据库抽样 seed=20260921）

| 场景 | Incident | 工作流完成 | 根因评分 | NO_CODE_PATCH / sandbox | 恢复前后观测 |
|---|---|---|---|---|---|
| slow_query | 2a17e25e-edd5-4d4a-b2bf-9fe83ff94461 | True | True | NO_CODE_PATCH | Observer before/after |
| cache_miss | b56a5385-7b78-4902-bb57-53824496cc99 | True | True | NO_CODE_PATCH | Observer before/after |
| consumer_lag | ec7d655c-a60e-4016-9ee0-cc03dee77537 | True | True | NO_CODE_PATCH | Observer before/after |
| retry_storm | e3c025bb-a72d-4564-9441-05fb62dd11fd | True | False | NO_CODE_PATCH | Observer before/after |
| code_exception | 5c35b598-4ef3-447c-ba7a-b17b4e68801b | True | True | CODE_PATCH | Sandbox replay |

最终 Critic 分布：`{"PARTIALLY_VERIFIED": 6, "VERIFIED": 2}`。

外层真实观测（每格为故障前 → 故障中 → 控制端恢复后；这些窗口不计为 AI 修复）：

| 场景 | Gateway 错误率 % | Gateway P95 ms | Kafka lag |
|---|---|---|---|
| slow_query | 0 → 0 → 0 | 68.08 → 1,259.73 → 82.55 | 0 → 0 → 0 |
| pool_exhaustion | Unknown → 50 → 0 | Unknown → 817.94 → 52.99 | Unknown → 0 → 0 |
| n_plus_one | 0 → 0 → 0 | 78.08 → 136.44 → 76.86 | 0 → 0 → 0 |
| cache_miss | 0 → 0 → 0 | 74.41 → 68.29 → 63.48 | 0 → 0 → 0 |
| consumer_lag | 0 → 0 → 0 | 89.66 → 81.31 → 51.78 | 0 → 90 → 0 |
| downstream_timeout | 0 → 50 → 0 | 49.92 → 2,016.1 → 55.24 | 0 → 0 → 0 |
| retry_storm | 0 → 50.34 → 0 | 51.41 → 94.04 → 55.35 | 0 → 0 → 0 |
| code_exception | 0 → 49.69 → 0 | 56.3 → 34.56 → 59.69 | 0 → 0 → 0 |

### Context Optimized V3（数据库抽样 seed=20260921）

| 场景 | Incident | 工作流完成 | 根因评分 | NO_CODE_PATCH / sandbox | 恢复前后观测 |
|---|---|---|---|---|---|
| slow_query | 6b7ecbb4-008e-4729-9209-7006925c8080 | True | True | NO_CODE_PATCH | Observer before/after |
| cache_miss | d868b46a-ab64-4273-8da2-1959a7f84d2f | False | False | 无有效诊断 | 仅实验外层测量/未闭环 |
| consumer_lag | 56a92b73-d912-4623-97ad-9dd391583898 | False | False | 无有效诊断 | 仅实验外层测量/未闭环 |
| retry_storm | e7cf2cef-c707-40df-9fa2-ab3d075052ac | True | False | NO_CODE_PATCH | Observer before/after |
| code_exception | 4c421e4c-0cb2-4c24-bb27-3fda222cb5d2 | False | False | 无有效诊断 | 仅实验外层测量/未闭环 |

最终 Critic 分布：`{"VERIFIED": 1, "NO_CRITIC": 6, "PARTIALLY_VERIFIED": 1}`。

外层真实观测（每格为故障前 → 故障中 → 控制端恢复后；这些窗口不计为 AI 修复）：

| 场景 | Gateway 错误率 % | Gateway P95 ms | Kafka lag |
|---|---|---|---|
| slow_query | 0 → 0 → 0 | 64.07 → 1,257.04 → 53.24 | 0 → 0 → 0 |
| pool_exhaustion | 0 → 50 → 0 | 58.72 → 820.16 → 54.92 | 0 → 0 → 0 |
| n_plus_one | 0 → 0 → 0 | 56.06 → 90.83 → 75.59 | 0 → 0 → 0 |
| cache_miss | 0 → 0 → 0 | 57.31 → 66.5 → 66.61 | 0 → 0 → 0 |
| consumer_lag | 0 → 0 → 0 | 57.9 → 60.61 → 69.1 | 0 → 93 → 0 |
| downstream_timeout | 0 → 51.16 → 0 | 77.73 → 2,018.4 → 100.92 | 0 → 0 → 0 |
| retry_storm | 0 → 50 → 0 | 78.61 → 121.15 → 76.93 | 0 → 0 → 0 |
| code_exception | 0 → 50 → 0 | 75.13 → 44.38 → 60.55 | 0 → 0 → 0 |

## 新实验逐项预测与评分理由

### Hybrid V2 / slow_query

**预测服务**：inventory-service

**预测根因**：inventory-service's GET /products handler issues an unconditional SELECT pg_sleep(1.2) against Postgres on every request, adding a fixed ~1.2s stall. This is not a genuinely slow query: pg_stat_statements shows the real products SELECT (SELECT id,name,price,stock FROM products ORDER BY id LIMIT $1) at mean_exec_time 0.108ms, while SELECT pg_sleep has mean_exec_time 1202ms. Live pg_stat_activity shows multiple 'active' SELECT pg_sleep(1.2) sessions with application_name=inventory-service. inventory-service /products logs are all HTTP 200 at ~1206-1214ms (no errors). The stall sits on the order-service /checkout critical path: a trace shows order-service's GET http://inventory-service:8000/products client span lasting 1.21s, which propagates up so that gateway, order-service and inventory-service all plateau near 1.2s p95. Redis and Kafka are healthy (TTL 30; consumer lag 0), and payment/user/notification remain fast, ruling them out.

**原始评分 / 失败说明**：Diagnosis correctly identifies the causal mechanism: inventory-service issues SELECT pg_sleep(1.2) against Postgres before/around the catalog query, producing the ~1.2s stall. Supported by independent observations: live pg_stat_activity showing active PgSleep wait_event with application_name=inventory-service (E-041af48eda94420f, E-8e6072ae7bf94f16), inventory-service /products logs at ~1206-1214ms (E-b3e93f3dbda64027), and metrics showing the ~1.2s plateau across inventory/order/gateway (E-9d495c1f0b4e4f71). The affected service (inventory-service) and the pg_sleep(1.2) mechanism match ground truth; Redis/Kafka exclusions are correct. Minor extra detail (pg_stat_statements mean_exec_time, order-service client span) is plausible and non-contradictory. Evidence quality 2: multiple independent sources (DB activity, logs, metrics) align.

### Hybrid V2 / pool_exhaustion

**预测服务**：inventory-service

**预测根因**：inventory-service issues `SELECT pg_sleep(2)` queries that block for 2 seconds per call. With a pool of only 4 connections (pool_max=4), four concurrent sleeps occupy every slot (pool_available=0), so ordinary /products queries must wait for a free connection. They exceed the 0.80s pool acquisition timeout and fail with `PoolTimeout: couldn't get a connection after 0.80 sec`, returning HTTP 500 from inventory-service, which the gateway surfaces as HTTP 502 to the client (49.18% error rate at both gateway and inventory-service). pg_stat_statements shows two pg_sleep statements executed 164 and 745 times with mean exec times ~2.0s and ~1.2s, and live pg_stat_activity shows four active inventory-service backends in PgSleep/Timeout state. Latency (~800ms p95) matches the pool-timeout plus queueing behavior, not raw query cost. The shared postgres instance is not globally degraded: order-service, payment-service, user-service and gateway all keep pool_available>=1-3 with zero or negligible errors.

**原始评分 / 失败说明**：The diagnosis correctly identifies the category (DB_POOL_EXHAUSTION) and the affected service (inventory-service), and materially matches the ground truth mechanism: four concurrent long queries (SELECT pg_sleep(2)) occupy all four inventory pool slots (pool_max=4, pool_available=0), causing concurrent requests to fail acquiring a connection and raise PoolTimeout. This aligns with ground-truth root cause 'Four concurrent long queries occupy all four inventory pool slots' and the expected evidence PoolTimeout plus four active inventory SQL sessions. Evidence quality is 2: two independent observations support it — live DB activity (E-840386a43d404438) showing four active inventory-service sessions in PgSleep, and service logs/metrics (E-1220607725464ec8, E-bd5a0a649a7a4912, E-1b93cd05964f45c1) showing inventory-service 500 PoolTimeouts with pool_available=0 while other services stay healthy. The additional implementation details (exact pg_sleep call site, pool_max value) do not contradict the mechanism and the pg_sleep query is directly observed. No contradictory invented mechanism.

### Hybrid V2 / n_plus_one

**预测服务**：inventory-service

**预测根因**：The inventory-service product-detail path performs one database round-trip per product (N+1) instead of a single batched/set-based fetch. pg_stat_statements shows queryid -4386432147220479149 (SELECT id,name,price,stock FROM products WHERE id=$1) accumulating 7240 calls with calls_delta=280 in a 1s sample, and inventory-service db_qps spiking to ~122 q/s against a baseline of ~2.3 — a ~50x amplification. Critically, mean_exec_time is only 0.047 ms, so the SQL is not slow; the cost is the sheer number of near-identical statements repeated per request. The distributed trace of the checkout confirms the mechanism: inventory-service (process p3) emits roughly ten sequential child spans of the identical product SELECT (30–71 µs each) nested under one GET /products request. Because these lookups run sequentially against a shared AsyncConnectionPool bound at max_size=4 with timeout=0.8s, the per-request fan-out inflates wall time and drives pool wait (inventory-service requests_queued=20, requests_wait_ms=12853 cumulative). order-service and gateway latency are upstream symptoms accumulating this per-product cost, not independent faults. Redis cache misses compound exposure to the loop but are secondary; the primary defect is the unbounded per-item query loop.

**原始评分 / 失败说明**：The diagnosis correctly identifies the N+1 query root cause in inventory-service: the ground truth is 'One ID query followed by forty per-product SELECT statements' in inventory-service. The diagnosis pinpoints the identical SELECT id,name,price,stock FROM products WHERE id=$1 per-item loop, supported by independent sources: the DB activity snapshot showing repeated per-id product SELECTs for inventory-service (E-49fd1198c3b74acf/E-017012c92981444d) and the trace fan-out of identical product SELECT spans nested under one inventory-service request (E-9977251a90874e7a). It also correctly attributes inflated db_qps (~122-285 q/s vs ~3.7 baseline) to statement amplification rather than slow SQL. The mechanism (per-item loop, not a single batched query) and the affected service are materially correct, matching the ground truth and recovery method (restore batch catalog query). Pool/Redis details are secondary framing rather than contradictions. Two independent supporting observations establish evidence quality 2.

### Hybrid V2 / cache_miss

**预测服务**：inventory-service

**预测根因**：inventory-service's /products cache has been neutralized: the Redis catalog key does not exist (catalog_ttl = -2, i.e. key with no TTL / never set), and the read path itself deletes it. Traces show each GET /products executes EXISTS, GET (miss), then DEL against Redis before falling through to Postgres `SELECT id,name,price,stock FROM products ORDER BY id LIMIT 40`. Because the key is deleted on every read (or never repopulated), 100% of requests hit the database. This raised inventory-service db_qps from a ~0.16 baseline to ~7.4 rps — a ~45x amplification — visible both in Prometheus db_qps windows and in pg_stat_statements call deltas for the product query. HTTP latency remained low (~4ms) and errors 0, so this is a cache-effectiveness/invalidation regression producing DB amplification and pool pressure, not a latency or availability outage.

**原始评分 / 失败说明**：The submitted diagnosis correctly identifies the ground-truth root cause category and mechanism: Catalog reads bypass the cache and the read path itself deletes/invalidates the catalog key, causing every GET /products to fall through to Postgres. This matches the ground truth ('Catalog reads bypass cache and invalidate catalog key') and the affected service inventory-service. Evidence is materially correct and independently corroborated: (1) catalog_ttl=-2 across multiple Redis snapshots (key absent), (2) inventory db_qps amplification (~0.16 baseline to ~7.4 rps) while request_rps stayed flat, (3) traces showing DEL on the read path plus Postgres fallthrough, and (4) pg_stat_statements call deltas on the products query. The diagnosis additionally reports the read path issuing a DEL against Redis, which is consistent with the injected fault; accepting this higher-level mechanism is warranted. Two or more independent supporting observations are present, so evidence quality is 2.

### Hybrid V2 / consumer_lag

**预测服务**：notification-service

**预测根因**：notification-service's Kafka consumer has stopped consuming from redpanda partition 0. Across three snapshots the group committed_offset stayed frozen at 33150 while end_offset advanced (33243 → 33289 → 33352), so lag grew monotonically 93 → 139 → 202 entirely from producer writes; consumer_rps was 0.0. HTTP health stays green (200, healthy), pool-stats show 0 waiting/1 queued, and in-window notification-service logs contain only /pool-stats self-probes with no consumer or poll errors. This pattern indicates a silently blocked or dead consumer loop — not a crash (no errors), not slow processing (committed offset would still advance), and not backpressure from DB/Redis pools (no waiting). Producer side (order-service checkout) continues normally with healthy HTTP latency and 0% errors, so the impact is isolated to asynchronous notification delivery.

**原始评分 / 失败说明**：The diagnosis correctly identifies the CONSUMER_LAG scenario on notification-service: the Kafka consumer on redpanda partition 0 is stalled, with committed_offset frozen at 33150 while end_offset advances and lag grows monotonically (93→139→202). The affected service, category, and causal mechanism (consumer not consuming/committing causing backlog) materially match the ground truth. Evidence is strong: three independent inspect_kafka snapshots (E-4a7d0f551bd64a6c, E-69a8d3ec3d034e51, E-3a6a182ee6d94ab6) independently corroborate frozen committed offsets and rising lag, with notification-service in-window logs showing only /pool-stats self-probes. The diagnosis rules out alternative causes (crash, slow processing, pool backpressure) appropriately and recommends operational recovery to drain the backlog, consistent with ground truth. The higher-level mechanism is accurate even without specifying the exact injection implementation.

### Hybrid V2 / downstream_timeout

**预测服务**：order-service

**预测根因**：Failing trace 1feb060fcd91440def2fe8f112df0716 shows the gateway's client span POST http://order-service:8000/checkout with duration_us=2005324 (~2005ms) and otel.status_description \"ReadTimeout:\" → HTTP 502. In the same trace, downstream calls complete in microseconds/milliseconds (payment POST /charge ~35us, user SELECT ~24us, inventory GET ~243us), so no downstream service or shared pool is the source. Order-service /checkout error logs all show near-identical ~2018ms durations with status 502 — a fixed injected delay — and pg_stat_statements records SELECT pg_sleep($1) with mean_exec_time ~1202ms over 531 calls, an active delay-injection primitive. The delay sits inside order-service's request path; gateway's ReadTimeout converts the slow call into 502s, so gateway's 502s are derived, not independent.

**原始评分 / 失败说明**：The submission's category (DOWNSTREAM_TIMEOUT) and its identification of the mechanism (a ~2s injected delay causing the caller's ReadTimeout and 502) are partially right, but it places the root cause in the wrong service. Ground truth: the affected service is payment-service, whose processing is delayed 3 seconds while the caller's (order-service) timeout is 2 seconds. The observed metrics support this: payment-service shows ~3006ms latency while all others are at most ~2s, meaning the delay is in payment-service and order-service hits its ReadTimeout waiting on payment. The submission instead claims the delay lives inside order-service's own request path and treats payment-service's latency as a fast child span/symptom, directly contradicting the immutable ground truth (payment delay > caller timeout). Because the mechanism is attributed to the wrong service, the causal chain is materially incorrect, even though it correctly observed the downstream-timeout pattern and 502s. Evidence quality is 2: multiple independent supporting observations (failing trace, paired gateway/order-service logs with matched trace IDs, latency metrics showing payment-service at ~3s).

### Hybrid V2 / retry_storm

**预测服务**：payment-service

**预测根因**：payment-service fails /charge almost instantly (~1.3-2.0ms, HTTP 503) rather than timing out. The trace for b0860c751bde1cb7d4a67a318084791a shows payment-service (p4) issuing a Redis EXISTS call (~284us) and then returning 503; the httpx client span from order-service shows the same 503 with ERROR status. Redis cumulative counters show keyspace_misses (138,852 -> 142,111) far exceeding keyspace_hits (29,385 -> 32,220), consistent with the Redis lookup/guard that gates charging missing for the traffic being charged. Independently, Postgres is healthy (all sessions idle in ClientRead, product statements execute in ~0.05-0.11ms mean, zero call_delta between snapshots) and Kafka lag is 0, so this is not DB slowness, pool exhaustion or consumer lag. Log timestamps show payment 503 at 11:08:40.083943, then order-service 502 at .090135, then gateway 502 at .095378 (trace de3e5d375a95384a5c533d783c5804c6), establishing payment-service as origin; order-service issues ~5 requests per checkout (ratio 4.95, intervals ~7-8ms) which amplifies but does not originate the errors. Exact upstream of the Redis miss (key eviction, TTL/catalog:11 expiry, or a stale guard key) is not directly visible in-scope.

**原始评分 / 失败说明**：The ground truth root cause is a retry storm: order-service issues five immediate retries per failed payment call without backoff, amplifying failures. The diagnosis instead attributes the origin to a Redis-backed CACHE_MISS guard in payment-service causing /charge to return 503. While the diagnosis does note order-service's 5x retry ratio (~4.95), it explicitly treats this as downstream amplification, not the root cause, and places the causal mechanism on an invented Redis cache-miss guard. This is a materially different mechanism and an incorrect category (CACHE_MISS vs retry storm). The observed fast payment 503s and the 5 retries are consistent with the retry-storm scenario, but the submission's causal explanation contradicts the ground truth. Evidence is well-supported by two independent observations (traces/logs and metrics showing the retry ratio), so evidence quality is 2.

### Hybrid V2 / code_exception

**预测服务**：order-service

**预测根因**：`services/pricing.py::total` (lines 3-6) declares `discount: float | None = 0` but computes `round(price * quantity * (1 - discount), 2)` without normalizing None. When checkout calls total() with discount=None (which the acceptance contract treats as "no discount"), Python evaluates `1 - None` and raises `TypeError: unsupported operand type(s) for -: 'int' and 'NoneType'`. order-service's /checkout handler therefore returns HTTP 500, and gateway, which calls order-service, propagates this as HTTP 502 on POST /checkout. All dependency layers are healthy: inventory-service child spans return 200, redis spans are sub-millisecond, postgres sessions are idle with no query buildup, and Kafka lag is 0. This is a local pure-code bug in the order pricing function, not an infrastructure fault.

**原始评分 / 失败说明**：The diagnosis correctly identifies the causal mechanism and service: services/pricing.py::total() computes `price * quantity * (1 - discount)` while discount may be None, raising `TypeError: unsupported operand type(s) for -: 'int' and 'NoneType'`, which makes order-service POST /checkout return 500 and gateway propagate 502. This matches the ground-truth root cause (pricing.total subtracts None discount from integer) and affected service order-service. Two independent supporting observations exist: order-service logs showing repeated TypeError on /checkout (E-3bfb50c849db41b1) and trace detail showing the gateway 502 / order-service 500 chain with healthy child spans (E-6a842bd870a14b90). The recommended fix (normalize None discount to 0) is materially correct and the proposed patch validated error_pct 0.0.

### Context Optimized V3 / slow_query

**预测服务**：inventory-service

**预测根因**：inventory-service's request path issues SELECT pg_sleep(1.2) against Postgres, adding a deterministic ~1.2s wait to every affected request. Postgres active sessions attribute the PgSleep/Timeout waits to application_name "inventory-service", and inventory-service's db_qps rises ~20x over baseline (0.18 -> 3.96) while every other service's db_qps decreases. The resulting ~1.2s server-side delay propagates upward: order-service /checkout (p50 ~1234ms) waits on its inventory dependency (critical-path span 997066ac7daecce5 GET 1212ms inside order-service POST /checkout 1233ms), and gateway (p50 ~1246ms) waits on order-service. error_pct is 0.00 in every service, so this is a latency injection, not a failure or exception. The /products ORDER BY id list query itself is fast (call deltas are normal); the pg_sleep statement is the specific added delay, so a single code path introduces the latency rather than DB resource contention or pool exhaustion.

**原始评分 / 失败说明**：The diagnosis correctly identifies the causal mechanism: inventory-service executes SELECT pg_sleep(1.2) against Postgres, adding a deterministic ~1.2s delay per request on its /products path, which propagates to order-service /checkout and gateway. This matches the ground truth exactly (Inventory executes pg_sleep(1.2) before catalog SQL). Evidence is strong and independently corroborated: 4 inspect_database snapshots show active sessions running SELECT pg_sleep(1.2) with wait_event PgSleep/Timeout attributed to application_name=inventory-service, and query_metrics show inventory-service p50 ~1207ms matching the sleep while error_pct=0.00 everywhere. The affected service (inventory-service) is correct, the mechanism (artificial pg_sleep delay, not resource contention or pool exhaustion) is correct, and the recovery direction (remove the injected delay) is correct. The inability to locate the exact code line does not contradict the ground truth, which is an injected delay.

### Context Optimized V3 / pool_exhaustion

**预测服务**：None

**预测根因**：None

**原始评分 / 失败说明**：Investigation failed or produced no valid diagnosis. | Workflow error: {"code": "ValueError", "message": "HYBRID_STEP_BUDGET_EXCEEDED"}

### Context Optimized V3 / n_plus_one

**预测服务**：None

**预测根因**：None

**原始评分 / 失败说明**：Investigation failed or produced no valid diagnosis. | Workflow error: {"code": "ValueError", "message": "HYBRID_TOOL_BUDGET_EXCEEDED"}

### Context Optimized V3 / cache_miss

**预测服务**：None

**预测根因**：None

**原始评分 / 失败说明**：Investigation failed or produced no valid diagnosis. | Workflow error: {"code": "ValueError", "message": "HYBRID_TOOL_BUDGET_EXCEEDED"}

### Context Optimized V3 / consumer_lag

**预测服务**：None

**预测根因**：None

**原始评分 / 失败说明**：Investigation failed or produced no valid diagnosis. | Workflow error: {"code": "ValidationError", "message": "9 validation errors for InvestigationPlan\nsuspected_services\n  Field required [type=missing, input_value={'additionalProperties': ...Plan', 'type': 'object'}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/missing\ninitial_hypotheses\n  Field required [type=missing, input_value={'additionalProperties': ...Plan', 'type': 'object'}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/missing\ntool_priority\n  Field required [type=missing, input_value={'additionalProperties': ...Plan', 'type': 'object'}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/missing\nstop_conditions\n  Field required [type=missing, input_value={'additionalProperties': ...Plan', 'type': 'object'}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/missing\nadditionalProperties\n  Extra inputs are not permitted [type=extra_forbidden, input_value=False, input_type=bool]\n    For f"}

### Context Optimized V3 / downstream_timeout

**预测服务**：None

**预测根因**：None

**原始评分 / 失败说明**：Investigation failed or produced no valid diagnosis. | Workflow error: {"code": "ValueError", "message": "HYBRID_TOOL_BUDGET_EXCEEDED"}

### Context Optimized V3 / retry_storm

**预测服务**：payment-service

**预测根因**：payment-service /charge returns 503 on ~99.7% of requests in 2.8–4ms, i.e. a fast-fail before meaningful downstream I/O. Two independent sources corroborate: (1) sampled logs contain only payment-service /charge 503 ERROR groups (two 60-row samples, no other error-producing service), and (2) trace cf3813d839d20d97ce0e84da4a3a79f1 shows the causal chain gateway 502 -> order-service /checkout 502 -> order-service POST 503 -> payment-service POST /charge 503, while the payment-service child span EXISTS (redis) succeeds in 0.457ms with error=false. Database state is idle: all pg_stat_activity sessions (including payment-service) are idle in ClientRead, and pg_stat_statements call_deltas are all 0 with sub-ms mean exec times (pg_sleep test query excluded), so Postgres is not the bottleneck. Redis counters are cumulative hits/misses with no error component. Because a 503 is produced in milliseconds with healthy cache and DB dependencies, the fault is inside payment-service's charge path (error branch/exception/configuration of its own logic or payment-provider dependency), not a slow downstream. order-service's ~4.9x repeated /charge calls (5 calls, ~14–18ms intervals, request_ratio 4.95) amplify the load but do not originate the errors; gateway errors are pure propagation. NOTE: the exact error branch was not confirmed — the charge-handler source was not readable within the allowed scope (search_repository located references only; get_code_symbol/get_code_context not available/insufficient), so the precise internal trigger remains unverified and the deepest root cause is UNKNOWN.

**原始评分 / 失败说明**：The diagnosis correctly identifies the amplification mechanism (order-service issuing ~5 repeated /charge calls, ratio ~4.95, at ~15ms spacing) and correctly notes the fast-fail 503s and propagation, but it attributes the origin to payment-service /charge returning 503 on ~99.7% of requests, i.e. a payment-service internal fast-fail. Ground truth is a Retry Storm in order-service: immediate retries per failed call without backoff, amplified by a failing payment call. The affected/originating service is order-service's retry policy, not an internal payment defect. The diagnosis inverts origin and amplification—it treats order-service retries as mere 'amplification' and payment /charge as the origin—so the causal mechanism and service attribution are materially wrong. It also labels the deepest root cause UNKNOWN rather than the retry storm. Evidence quality is 2: independent supporting observations (trace chain, log groups, retry ratio metrics).

### Context Optimized V3 / code_exception

**预测服务**：None

**预测根因**：None

**原始评分 / 失败说明**：Investigation failed or produced no valid diagnosis. | Workflow error: {"code": "ValueError", "message": "HYBRID_TOOL_BUDGET_EXCEEDED"}

## 记录完整性

172 项记录检查，完整性通过=True。检查了 V2/V3 同一实验源码与实际容器哈希、16 个独立 run、工具与 Evidence 外键、模型名称与 usage 算术、终态后的评分调用、未自动 Apply 以及服务端恢复观测。实验后仅有明确记录的运维修复。故障有效性证据另见 `evaluation/fault-validity.json`，不是依据模型答对与否判定注入成功。完整性通过不等于所有根因或工作流通过。

## 最终运行状态与 UI 验证

交付检查通过=True；14 个 Compose 容器运行，37 个容器内 Python/Web 文件与当前交付源码一致。活跃故障=[]，流量开启=True，评估锁存在=False。详细时点和真实指标见 `evaluation/delivery-runtime.json`。

后台故障执行器修复后的真实占满/停止恢复验证通过=True，该检查没有调用模型，不进入准确率。浏览器验证通过=True：四组实测、图表切换、场景证据、Critic、失败原因、播放/暂停/末尾跳转均检查；最终浏览器无 console warning/error。见 `evaluation/ui-validation.json`。

## 重现与审计

```powershell
docker compose up -d --build
docker compose run --rm --no-deps sentinel python -m pytest -q -p no:cacheprovider tests/test_controls.py tests/test_agent_phase2.py tests/test_hybrid.py tests/test_worker_recovery.py
# 正式输出不可覆盖；另开有明确标记的实验文件才能做新实验。
python scripts/report_phase3.py
python scripts/audit_phase3.py
python scripts/audit_runtime_phase3.py
python scripts/verify_phase3_artifacts.py
python scripts/deliver_phase3.py
```

不要在冻结实验期间执行迁移、测试或重启。`evaluate_phase3.py` 会拒绝覆盖已有正式文件；只有调查终态后 Evaluator 才读取真值。V1 冻结 artifact 没有重新生成。

UI：http://localhost:18082/evaluation.html。场景单元格包含真值、预测、评分理由、证据、工具时间线、Provider 分角色用量，以及有明确录制标记的回放。
