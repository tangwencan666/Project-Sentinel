# 第三阶段失败分析

这里记录从正式原始结果可核查的问题，不用于向调查 Agent 提供答案，也不用于更改评分。

## V2 连接池：上下文预算终止

Incident `9aaeab70-193e-43a3-b687-55b2ec65edf4` 多次读取原始证据分页，在提交有效根因之前触发 `CONTEXT_BUDGET_EXCEEDED`。原始记录计为根因和定位失败，不能将工具执行成功当作调查完成。它与更早被明确中止的 Evidence ID 协议循环不是同一事件。后续证明其故障注入失效，所以原件保留，在首次有效试验集合中按预先声明规则单独替换；不抹去其真实框架失败和消耗。

**后续有效性核查**：V2 数据库快照及 V3 同场景的 7 次快照都没有活动占用查询，pg_sleep 调用增量为 0。原始判分必须保留，但不能把这两条当作已验证的连接池故障评估。`evaluation/pool-validity-investigation.json` 在补测之前记录了判断依据和处置规则；只有同镜像重启前后证明故障从不生效变为真实连接占满后，才允许各版本一次有效补测。补测不修改原始文件。

最终证明：原 inventory 后台任务因 Redis DNS ConnectionError 退出。同镜像重启前活动占用为 0，重启后连续三次活动占用为 4、可用连接为 0，HTTP 错误率约 48%–50%。V2 唯一有效补测 `bd325156-99e8-457d-8d41-b37145f3b984` 根因/服务正确、PARTIALLY_VERIFIED；V3 唯一有效补测 `7ca6ae39-20f5-41c2-aaf8-69f06f14edfa` 因 `HYBRID_STEP_BUDGET_EXCEEDED` 失败。原始 5/8、1/8 和首次有效集合 6/8、1/8 均明确展示。

V2 补测首次评分接口返回 HTTP 409，调查没有重跑；仅对同一终态运行重试评分。首次错误正文未保存，不能猜测其确切 schema 错误。两次评分模型调用的成功传输/usage 均在账本。实验脚本中止前未保存的外层健康窗口保持 Unknown；故障中和恢复后窗口取自该 run 的服务端 RecoveryObserver，不倒填新测量。

## V2 下游超时：把短内部 span 当作完整下游耗时

Incident `7141d125-48d0-4712-96e6-da1a2389b148` 把根因放在 order-service。原始判断引用微秒级内部 span 来排除下游，还把此前慢查询实验累积的 pg_sleep 统计当作当前延迟线索。原评分器指出，当前 payment-service 的实际约 3006 ms 延迟与调用方约 2 秒超时才匹配。

这是一次真实归因错误，不能靠代码里按 scenario_id 指定 payment-service 来修正。V3 已在冻结实现中统一保留慢 span/嵌套链，并对数据库优先提供当前活动与调用差分，减少累积统计干扰；实际效果以 V3 结果为准，不能先宣称解决。

## V2 Redis：主机制正确不代表所有措辞准确

Incident `b56a5385-7b78-4902-bb57-53824496cc99` 正确识别缓存删除与数据库查询放大，但对 TTL=-2 的解释混入了“没有 TTL”的表述，而且将样本观察写成“100% 请求”。这些措辞保留在原始记录中，没有为展示效果人工润色模型答案。Critic 为 PARTIALLY_VERIFIED。

## V2 重试放大：看见放大后仍虚构更深层机制

Incident `e3c025bb-a72d-4564-9441-05fb62dd11fd` 已注意到约 4.95 倍调用比，却把主要根因写为 payment-service 中的 Redis 缓存守卫失效。Trace 中的 Redis EXISTS 和累计 misses 不能证明存在这样一个收费守卫。原评分器据此判错；确定性 Verifier 虽为 PASS，独立 LLM Critic 只给 PARTIALLY_VERIFIED。这说明结构门禁并不能排除模型编造因果解释，仍需要查看语义判断和原始证据。

## 开发预检与正式结果分离

早期 Planner schema 失败、三次真实重启后预算终止，以及首次 V2 Evidence ID 格式循环的记录均独立保存。`evaluation/interruptions.json` 写明中止原因和泛化修复；`evaluation/comparison.json` 的 development_usage 按调用 ID 去重计入额外已知消耗。正式错误不会被重跑并替换成成功结果。

完整八场景的新预测、评分理由和最终失败分布由 `scripts/deliver_phase3.py` 从原始账本生成，见 `evaluation.md`。单次实验和同模型评分存在局限，应同时阅读原始证据、工作流状态、Critic 和根因评分。

## V3 N+1：压缩没有消除工具协议失败

Incident `b55d060f-3a7c-472b-933e-9e9a698aab37` 在预算收敛阶段继续请求未提供的 read_evidence，随后根因提交包含未读取的代码引用，最后一次参数不是合法 JSON。执行层拒绝越过能力和引用边界，最终为 `HYBRID_TOOL_BUDGET_EXCEEDED`。这是真实 Agent 失败，保留在有效评估分母中，不按“缺少更多 tokens”自动重跑，也不与注入未生效的连接池实验混同。

## V3 缓存与 Kafka：输出协议可靠性仍不足

缓存 Incident `d868b46a-ab64-4273-8da2-1959a7f84d2f` 同样因未提供工具、未读代码引用和非法 JSON 触发预算终止。N+1 与缓存的非法 JSON 调用都恰好输出 2500 tokens，符合输出上限截断的可能性；当前账本没有保存 finish_reason，不能把这一推断写成已证实的事实。

Kafka Incident `56a92b73-d912-4623-97ad-9dd391583898` 的 Planner 回显了 JSON Schema，而不是符合 schema 的计划对象，校验失败。当前 Planner 没有自动修复 schema 回显的重试环节。这些失败说明 V3 输入压缩没有解决结构化输出和收敛的全部问题；较低 tokens 也包含提前失败造成的减少。
