# 面试前五分钟 · 架构速记

**一句话：**把“结账报错”变成可审查的工具证据、根因与沙箱验证候选。

| 要讲的路径 | 实际流程 |
|---|---|
| 核心组件 | Dashboard → Incident API → 自建 Agent Runtime → 工具 → 六个微服务与 PostgreSQL/Redis/Kafka。 |
| 数据流 | HTTP → 服务调用/SQL/缓存/消息；OpenTelemetry 与指标、日志提供关联数据；工具结果进入 Evidence 账本。 |
| Agent 流程 | Triage → Planner → Tool → Evidence → Hypothesis → Validation → Root Cause → Fix eligibility → Critic → Report。 |
| 错误恢复 | ToolError/结构化错误 → 显式状态和保留反馈 → 有界修复 → Checkpoint/Resume；不是无限重试。 |
| Fault 流程 | 操作员触发 → 真实业务异常 → 创建 Incident → 调查 → 实验恢复；ground truth 由隔离评分器使用。演示 incident 是 operator-requested。 |
| Patch 流程 | 模型提交替换源码 → 控制器计算 diff → 路径/函数/AST 校验 → 原合同失败记录 → 候选合同 → 三服务真实依赖重放 → 高风险候选人工审查；NOT DEPLOYED。 |
| Evaluation 流程 | 八场景首次运行 → 保存工具/模型用量/结果 → 根据隔离真值评估 → 保留失败/混杂项 → 比较完成率、正确率、成本与延迟。 |
| Public 流程 | 浏览器 → 只读 API → 冻结文件；不加载 Live Agent、数据库驱动、密钥或故障工具。 |

**阅读数字时区分版本：**6 服务 / 8 故障；历史 V3 完成 2/8；冻结 V4.1 完成 8/8、根因 7/8，累计 1,461,870 workflow tokens、78.75 秒均值。189 项是 Benchmark 当时的测试门禁，287 后端与 17 前端是历史独立审计记录；当前源码加入引用保护后未重跑完整付费 Benchmark。各批次证据见 [测试索引](TEST_EVIDENCE.md)，本次文档验证见 [2026-10-22 记录](validation-20261022.md)。

**必须主动说的边界：**八场受控样本、单模型、重试风暴仍错、Critic 全部部分验证、实验 helper 可见、沙箱共享内核。停止注入 ≠ 代码修复；测试通过 ≠ 生产部署；录制 ≠ 现场新调查。
