# V1 失败分析（原始评分不变）

数据取自冻结的 `evaluation/baselines/archive.zip` 内 `docs/phase2-run-ledger.json`。以下是工程分析，不是重新评分，也不作为 Investigator 输入。原始三次失败和 Kafka Critic 误放行必须保留。

| 场景 | 实际看见的证据 | 缺失或未利用的证据 | 调查顺序与噪声 | 服务定位与过度依赖 |
|---|---|---|---|---|
| Redis | `E-5d775c7b244742e8` catalog TTL=-2；`E-e19db2b0f7d3487f` 一秒内目录 SELECT 增加 10 次；`E-7435528032dc4b43` 所有服务 HTTP 错误率 0 | 没有目录级缓存命中率，也没有与健康窗口的数据库调用比率；没有将缺失缓存和当前 SQL 增长联合解释 | 先完整扫 logs/metrics/health/DB/Redis/Kafka，再多次读取 runtime/pricing 和分页证据。大量累计历史 SQL 与可用源码范围限制分散注意力 | 服务 inventory 正确，但推断“没有故障”；过度依赖 HTTP 低延迟、无错误。排除历史 pg_sleep 干扰本身是正确行为 |
| Kafka | `E-40f7f1a7d1f149a6` end=17083、committed=16903、lag=180；HTTP 全部健康 | Investigator 只查了一次 Kafka，未拿到 lag 变化、生产/消费速率；后续 RecoveryObserver 的恢复前后证据存在于完整账本 | Kafka 后继续查源码、Trace、Redis、health，并多次分页，没有优先复查队列进度 | 错误定位 inventory；将 HTTP 正常推及异步系统健康，Critic 仍给 VERIFIED |
| Retry | `E-2448366dff684bbe` 同一窗口 payment=352 次、order=72 次（约 4.89 倍）；payment ~99.72% 错误、P95 约 5.23ms；真实 Trace 中有支付 503 | 没有显式提取同一 Trace 下 client span 的重复次数与重试间隔；没有把请求放大归到调用方 | 开头全系统扫描，之后大量源码搜索、读文件、分页日志；未按 caller→callee 组织证据 | 判成 payment 快速失败，遗漏 order 重试策略造成的放大。将下游症状当成主要根因，服务也错 |

V2 使用通用的、引用真实 Evidence ID 的预检信号：缓存缺失与当前 SQL 增长、Kafka 两次 offset 快照、连接池实时压力、Trace 重复客户端调用与 HTTP 请求比率。它们都是调查建议，不输出最终根因类别。

Planner 根据这些信号、拓扑和观测摘要决定后续工具顺序。Investigator 必须独立验证。确定性验证器要求两个独立来源、有效服务引用、每条信号的处理结果，以及真实测试/重放材料；它只能约束证据完整性，不能证明语义正确。

V3 再对日志聚类、指标窗口、Trace 调用路径和源码函数进行压缩。上述改进是否有效，只能由新的冻结实验确定，不能从设计直接宣称准确率提升。

源码覆盖面的限制尚未消失：`services/app.py` 把业务逻辑与故障控制写在同一文件。直接将它开放给调查工具可能暴露注入条件。当前只允许读取 pricing/runtime/定价合同测试，payment 和 inventory 通用代码 Patch 仍未实现。
