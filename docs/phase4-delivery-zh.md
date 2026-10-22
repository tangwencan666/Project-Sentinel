# Phase 4 交付记录：中文导读

[文档导航](index.md) · [2026-09-22 英文原始记录](phase4-delivery.md)

冻结 `deepseek-chat` / `sentinel-benchmark-v2` 首轮完成 8/8，根因/服务 7/8，1,461,870 工作流 Token、284 工具调用、平均 78.75 秒。重试风暴误判，八场 Critic 全为 `PARTIALLY_VERIFIED`，未部署候选。

| 阶段 | 交付内容 |
| --- | --- |
| A–C | 四类基线封存、显式状态/固定上下文/六类预算/读取登记/响应日志与回执；初始 81、最终 189 项门禁 |
| D–F | V3.1 首轮 1/8，后续资格 5/5；Evidence Compiler；V4 首轮 7/8 完成、5/8 根因，两场混杂保留 |
| G–H | 四类真实模型组件候选、三服务与真实依赖；SIGKILL/exit 137、同 run 恢复、失败与后续结果、协议及注入探测 |
| I–K | SSE/诊断/录制与导出、历史版本与独立发布面板；API/数据库/浏览器审计；八次首派及冻结工件 |

结果 SHA256 为 `74b48f0cc7a3f341ca0a088a50054fa0c45209034d12aa4f5de46a4f1fa2c81a`，当时镜像 tag 为 `project-sentinel:phase4-v4.1-first`。原始内部结果、源码归档、镜像 ID、失败实验、实际测试与健康快照路径见原文，它们不是本轮新测试。

源码包排除 `.env`、Git 内部、镜像/数据卷、字节码和旧交付 ZIP，内部历史源码包另行保存。Git 发布不含全部 `evaluation/` 和 `outputs/`；公开仓库使用 `portfolio/data/` 的脱敏投影。

原文的 `18082` Live 入口属于冻结部署布局。当前默认 `18082` 是 Recorded Demo；Live Lab 使用 `compose.live.yaml`、`18083` 和显式 `LIVE_AI_ENABLED=true`。当前操作请看 [部署文档](deployment-public-demo.md)，不要照旧入口重跑付费实验。
