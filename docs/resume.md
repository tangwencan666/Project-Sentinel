# Resume material

## 中文（最多四条）

- 构建 Project Sentinel，基于六个电商微服务、PostgreSQL、Redis、Kafka 与 OpenTelemetry，通过 Hybrid Agent Tool Calling 实现真实事故观测、证据引用和根因报告闭环。
- 实现持久化 Agent Runtime：显式状态、分离预算、假设状态机、有界结构化修复、引用登记及 Checkpoint；完成真实进程 kill/resume 验证，保留失败与恢复记录。
- 使用 deepseek-chat 完成 V4.1 独立八场景首轮评估，工作流完成 8/8、根因及服务定位 7/8，调查用量 1,461,870 tokens；公开 V3/V3.1 失败和跨版本比较限制。
- 实现四类受限业务函数修复候选与三服务沙箱验证；V4.1 pricing 候选通过 9 项合同测试及真实故障重放，未部署。Phase 4 冻结测试门禁为 189 passed，并提供无模型调用的录制 Demo。

## English (at most four bullets)

- Built Project Sentinel with six commerce microservices, PostgreSQL, Redis, Kafka and OpenTelemetry; implemented Hybrid Agent tool calling to connect real observations, evidence and root-cause reports.
- Implemented a durable agent runtime with typed state, separate budgets, hypothesis transitions, bounded structured-output repair, citation tracking and checkpoints; validated real process kill/resume and retained unsuccessful attempts.
- Evaluated deepseek-chat on eight first-run V4.1 scenarios: 8/8 completed workflows and 7/8 correct root/service diagnoses, using 1,461,870 workflow tokens; published failed V3/V3.1 experiments and comparison limitations.
- Added constrained candidate repair for four business-function profiles and a three-service sandbox; the V4.1 pricing candidate passed nine contract tests and real fault replay without deployment. Preserved the 189-test Phase 4 gate and built a no-LLM recorded demo.

这些描述不声称生产部署、企业采用、用户规模、统计泛化或自动修复上线。后续 Phase 5 测试数量见最终验收文件，不替换 189 的冻结含义。
