> Historical design note. Current Phase 4 runtime, compiler, generic sandbox and recovery evidence are documented in [phase4-runtime.md](phase4-runtime.md), [phase4-generic-patching.md](phase4-generic-patching.md) and [phase4-recovery-security.md](phase4-recovery-security.md).

# Context Engineering

V2 和 V3 使用同一 deepseek-chat、同一 Planner/Investigator/Verifier 流程；V3 启用结构化证据压缩。实验版本通过 `HYBRID_V2`、`HYBRID_V3` 显式区分。V1 冻结结果不参与修改或重新评分。

最终实测 V3 工作流 token 为 896,380，比 V2 1,531,642 少约 41.5%，但根因正确率从 6/8 (75%) 降为 1/8 (12.5%)，完成率从 8/8 降为 2/8。当前优化目标未达成，且较低用量混有提前失败影响。失败包括 Planner 回显 schema、未经读取的代码引用、输出参数非法 JSON，以及工具/步骤预算终止；不能仅从压缩比推断质量改善，也不能把所有下降都归因于压缩本身。

## 数据处理

1. 所有真实工具调用和完整结果先写 PostgreSQL；模型默认读取有预算的视图。
2. 日志在事故时间窗口内按 service、ERROR/INFO 筛选，最多 60 条样本；对数字/标识符归一化模板聚类，保留次数、首末时间和 Trace 示例。次数是查询样本内计数，不冒充全量日志数量。
3. 指标保留真实 HTTP 窗口，以及 Prometheus 最近 20 秒序列与事故创建前 30 秒的参考点。参考点不是经过证明的健康基线。输出 baseline/current/delta/peak/trend；anomaly_score 是绝对相对变化，不是概率。缺失值保持 Unknown。
4. Trace 摘要保留最长嵌套 span 链、慢 span、错误 span、跨服务边、重复 client 调用、调用间隔和 fan-out。嵌套链是关键路径近似，不能相加重叠 span 的时长。原始 span ID、startTime、references 仍在账本。
5. 代码通过 `search_repository` 找位置，`get_code_symbol` 读取最多 80 行的实际函数/类，`get_code_context` 读取上下最多 20 行。路径仍受 allowlist 约束，不能读取实验注册表、配置和报告。
6. Evidence Pack 对摘要去重并排序，保留直接错误、相关服务、基础设施和代码。相同得分优先较新的观测，防止调查卡在最初快照。每包最多 16 项，Trace/代码分别最多 3 项，每项最多约 3200 字符，Investigator 主包预算 14000 字符。

## 预算与恢复

工具输出默认压缩后交给模型，原始证据由 `read_evidence` 按字符页读取，`get_trace_detail` 用于指定 Trace。消息长度超过 23000 字符后，在完整工具批次边界重建上下文，保留初始信号、计划、假设、最近 16 次工具调用和最近 3 页按需读取结果。每个证据都保留 ID，包内记录采集时间。

初始开发预检发现：只压缩 Evidence 而丢掉工具历史和按需读取结果，会导致模型反复读取相同页；仅按异常排序又会使旧错误快照长期占据上下文。这些失败保留在 `evaluation/resume-live*.json`，相应的上下文和收敛修正发生在正式八场景实验之前。

最多 12 次 Investigator 模型轮次、28 个 Investigator 工具请求、单次最多 6 个工具。接近上限时只提供假设和根因提交工具；工具执行层再次校验当前阶段允许的名称。证据不足应报告 UNKNOWN 和不确定性，不能为了结束而声称修复或 VERIFIED。

具体在使用 20 个工具或达到第 9 个模型回合时，通过 named `tool_choice` 要求记录假设或提交判断。提交仍经过相同的引用、来源和矛盾校验。V2 的旧上下文预览可能在达到这一条件之前触发字符上限；正式连接池实验已出现这种失败，结果保留，不能把预算终止计为一次有效诊断。

## 用量口径

Provider 返回的 input/output/total tokens 标为 **Measured**，调用账本保留成功、失败和中断。中断请求的服务端消耗可能未知，不能假定为零。

Raw/Compressed Evidence 的大小以 `字符数 / 4` 标为 **Estimated**，不作为实际 token 用量。它们只表示上下文构造时的快照，不应跨多次相同包相加声称“节省了多少输入”。实际节省比例仅用各版本 Provider 账本、相同工作流口径比较。评分器用量单列，费用因未配置单价保持 Unknown。

这些估算也不是完整请求大小：V3 raw 统计证据 payload，压缩侧包含摘要和引用元数据；V2 旧预览的 raw 统计完整 evidence JSON。角色提示、工具 schema 和对话历史另占输入。因此跨版本节省结论必须依据实际 Provider tokens，不能直接比较不同构造阶段的字符压缩率。

压缩存在丢失线索的风险；V3 是否优于 V2 必须看真实实验结果。源码覆盖、有限 Trace 样本和单次小样本评估也是限制。
