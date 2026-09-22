# 面试深挖路线

回答原则：先解释实际问题，再打开证据，最后说边界。问题编号对应 [核心 Q&A](interview-qa.md)。

| 层级 | 建议时间与页面 | 可能的问题 | 回答与证据落点 |
|---|---|---|---|
| Level 1 · HR / 非技术 | 30 秒–1 分钟；Overview | 做什么？你完成了什么？效果如何？ | Q1、Q36；结账事故、真实回放、8/8 完成与 7/8 正确。用 [30 秒讲稿](pitch-30s.md)，不先讲 Runtime 名词。 |
| Level 2 · 后端工程师 | 3–5 分钟；Architecture → Evidence → Patch | 如何查连接池、N+1、Redis、Kafka？日志与 Trace 如何关联？Patch 如何验证？ | Q22–25、Q39–41、Q48；展示真实工具证据与九项合同测试，不把健康接口当作消费者正常的证明。 |
| Level 3 · AI 应用工程师 | 5–10 分钟；Replay → Evaluation | Tool Calling、Hybrid、Ground Truth 隔离怎么实现？为何不用 RAG？为什么成本高？ | Q4、Q8–10、Q13–16、Q38、Q42；展示工具账本、引用、输入 token 和读权限边界。 |
| Level 4 · Agent / AI Systems | 10 分钟后；失败记录、Runtime 源码 | 压缩为什么导致失败？恢复的一致性边界？预算怎么分？Critic 有什么系统性缺陷？ | Q5–7、Q12、Q17–18、Q43–46；[V3 复盘](v3-failure-story.md)、原始失败记录、同一 Run 的 checkpoint。 |

遇到统计与生产问题，先承认八场景、单模型、受控流量、同模型 Critic 和共享内核等限制；不要把推测说成已经验证的能力。尖锐追问见 [24 个难题](interview-hard-questions.md)。
