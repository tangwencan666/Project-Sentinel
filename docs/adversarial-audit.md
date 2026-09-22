# 第三阶段敌对审计

审计目标是尝试推翻“真实、隔离、可验证”的声明，而不是只验证 HTTP 返回 200。自动记录位于 `evaluation/audit.json`、`evaluation/runtime-audit.json`，测试边界见 `tests/test_agent_phase2.py` 和 `tests/test_hybrid.py`。

## 数据和真值入口

扫描 `mock / fake / hardcoded / scenario_id / ground_truth / TODO / FIXME` 的源码位置。命中主要来自 Fault Lab 控制 API、场景注册表、事后评分器、实验脚本、审计和边界测试，以及操作员评估页面。`storage.py` 的 scenario_id 只是评分表字段，调查工具不能查询该表。新 Hybrid、Planner、Context 和 Verifier 没有 scenario_id 分支，也没有导入评分器或注册表。

工具没有任意 HTTP、shell、SQL 或文件写入入口。源码路径采用 allowlist；`.env`、场景定义、混有故障逻辑的 `services/app.py`、评估报告和路径穿越均被拒绝。原始证据读取受当前 run 约束，虚构或跨 run 引用不能通过。工具执行还校验角色和当前提供的能力，模型自行拼出的工具名不能突破阶段限制。

这不是进程隔离证明。调查和评分共享 API 进程、PostgreSQL 实例；主机管理员、任意代码执行漏洞或未来新增的宽泛工具可能破坏此边界。Operator API 当前也不是面向公网的多租户权限系统。

## 伪造观测与评分污染

正式试验运行期间，故障、业务代码、定价合同和评分器与 V1 冻结版本逐字节比对。主表没有重新运行或改变 V1 的评分，包括已知 Kafka 错误 VERIFIED、Rule retry_storm 的争议原分和历史 Patch 失败。试验后 `services/app.py` 增加后台任务 RedisError 重试，文件字节因此变化；审计明确报告这一差异，并通过 AST 限定为该异常包装，原故障 SQL/并发/处理器不变。精确试验源码保存在 `evaluation/frozen-framework.zip`。API 的三处默认 V3→V2 变更也单独核对。

协议错误测试会启动一个明确标记的本机 HTTP failure harness，用于真实触发 429、500、401、超时和非法 JSON；它不进入 Agent 准确率。日志样本计数、配置拓扑边、字符 token 估算都标记来源和局限。模型 tokens 来自 Provider usage；缺失用量和费用保持 Unknown。

恢复由实验控制端停止注入，再由服务端采集 Before/After；不能称为 AI 修复。Patch 只承认实际合同测试和 HTTP baseline/candidate replay。录制回放使用独立端点及 RECORDED RUN 标记，没有播放预写好的模型答案来冒充实时调查。

## 无法被结构检查解决的风险

- 两种证据族不一定统计独立；同一批请求可能同时产生日志、指标和 Trace。
- 确定性 Verifier 只校验证据结构、可追溯性和实际测试，不证明根因语义正确。LLM 仍可错误排除冲突；每条最终预测仍由原评分器单独评判。
- Investigator、Critic、Evaluator 使用同一模型，各自独立会话仍可能产生相关错误；每场景一次实验不足以推断总体成功率。
- V2 原始证据分页存在重复读取和上下文溢出风险；V3 摘要也可能丢失关键字段。失败和中止轮次必须保留。
- checkpoint 能恢复同一 run 和已提交证据，但不能承诺远端模型调用和所有 Patch 副作用 exactly-once。重启预检的最终状态必须和恢复证据分别报告。
- 通用 payment、inventory、order handler Patch 未完成。当前 pricing 沙箱不代表整个微服务栈的隔离发布验证。

实测例子：V2 的 `cache_miss` 被原评分器判为根因正确，但原始预测把 Redis TTL=-2 的“不存在”与“没有 TTL”混在同一句话中；后者应区别于 -1。它还使用“100% 请求”的绝对表述，而现有证据主要是有限 Trace 和查询率窗口。这些文字瑕疵没有被修改或隐藏。准确率评分是对主要机制的判断，不是对报告每句话的事实认证。

正式实验完成后重新运行静态审计和数据库/容器日志的当前密钥精确匹配扫描。扫描只输出计数及文件名，不输出密钥或匹配行。零命中只说明本次扫描范围没有发现问题，不能当作未来无泄漏的保证。
