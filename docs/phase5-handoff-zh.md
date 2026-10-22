# Phase 5 交接与复核：中文导读

[文档导航](index.md) · [英文原始交接](phase5-handoff.md)

原文保留 polish 阶段和最终交付的先后关系。`outputs/` ZIP 和 `artifacts/` 日志是本地工件，不随 Git 发布；源码和公开录制在仓库中。原文的“下一步发布仓库”已是历史待办，不表示今天还没有远程仓库。

当时完成安全 Markdown 阅读器、十项渲染/安全单测和真实 90-span 录制回归；历史门禁为后端 267、前端 17、浏览器 37、公开 HTTP 42，没有真实模型调用，失败测试与浏览器尝试另存。

复核原则是每次使用新的输出名，保留旧报告。完整后端需 PostgreSQL/Redis/Kafka；浏览器需只读演示与浏览器。clean-start 会操作独立 Compose 项目，打包会产生新工件；它们不是翻译所需的自动步骤。原文全部命令保持在英文证据中，本轮只执行 [测试说明](testing.md) 的离线与静态范围。

当前默认启动 `docker compose up -d --build`，访问 `18082`；完整 Live 为 `compose.live.yaml`、`18083`，默认 `LIVE_AI_ENABLED=false`。不要为刷新中文界面重跑冻结 V4.1。未来核心研究使用新版本与授权，保留重试风暴、Critic 和实验 helper 限制。
