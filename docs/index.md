# Project Sentinel 中文文档导航

[中文首页](../README.md) · [英文首页](../README_EN.md) · [全仓库扫描清单](localization-inventory.md)

默认演示是无需密钥的 Recorded Demo。Live Lab 是单独启用的本地实验环境；历史成绩、当前源码验证、原始证据分别阅读。下列中文导读不覆盖英文原报告或机器数据。

## 第一次阅读

| 目标 | 阅读路径 |
| --- | --- |
| 快速判断项目定位 | [30 秒介绍](pitch-30s.md) → [项目状态](final-status-zh.md) → [架构速记](architecture-cheatsheet.md) |
| 理解 Agent 工程 | [Agent Runtime](agent-runtime.md) → [Tool Calling](tool-calling.md) → [Evidence / Checkpoint](evidence-checkpoint.md) → [Sandbox 与安全](sandbox-security.md) |
| 本地运行与验证 | [部署](deployment-public-demo.md) → [五分钟演示](demo-5min.md) → [测试说明](testing.md) → [本轮验证](localization-validation.md) |
| 评估可信度 | [冻结评测导读](phase4-evaluation-zh.md) → [独立审计导读](independent-final-audit-zh.md) → [声明矩阵导读](claims-matrix-zh.md) → [限制](limitations.md) |

## 架构、设计与技术选型

- [实际技术栈](tech-stack.md)、[当前 Runtime](agent-runtime.md)、[Tool Calling 权限](tool-calling.md)、[Evidence 与恢复](evidence-checkpoint.md)、[Sandbox 安全](sandbox-security.md)。
- [早期系统架构](architecture.md)、[早期 Agent 设计](agent-design.md)、[V2/V3 上下文工程](context-engineering.md)、[早期可靠性设计](reliability.md)。这些文件明确标注版本，早期 pricing 单路径限制不代表当前四类候选能力。
- [Runtime 历史演进](phase4-runtime-zh.md)、[V4 编译方法](phase4-v4-methodology-zh.md)、[候选实现导读](phase4-generic-patching-zh.md)、[恢复与安全实验](phase4-recovery-security-zh.md)。

## 使用、部署和面试材料

- [部署说明](deployment-public-demo.md)、[五分钟演示](demo-5min.md)、[十分钟技术演示](demo-10min.md)、[历史 Live 指南](demo-guide.md)。
- [30 秒](pitch-30s.md)、[一分钟](pitch-1min.md)、[三分钟](pitch-3min.md)、[项目介绍](project-pitch.md)、[面试深度地图](interview-depth-map.md)。
- [49 个核心问答](interview-qa.md)、[24 个进阶问题](interview-hard-questions.md)、[中英文简历](resume.md)、[三条简历版](resume-short.md)、[V3 失败复盘](v3-failure-story.md)、[后续规划](future-work.md)。

## 实验、审计与原始证据

[历史记录总索引](history-index.md) 列出每份英文报告的中文入口；[事故报告导读](incident-reports-zh.md) 解释自动生成报告；[全仓库清单](localization-inventory.md) 逐文件说明保留英文的理由。

补充历史中文材料：[V1 失败](v1-failure-analysis.md)、[V3 失败分析](phase3-failure-analysis.md)、[早期对抗审计](adversarial-audit.md)、[测试证据索引](TEST_EVIDENCE.md)、[2026-10-18 本地验收](LOCAL_ACCEPTANCE.md)、[2026-10-18 验证](PORTFOLIO_VERIFICATION.md)、[首轮首页中文化验证](validation-20261022.md)。

当前验证请看 [本轮记录](localization-validation.md)。`evaluation/`、`outputs/`、`artifacts/` 原路径常指未随 Git 发布的内部工件；保留引用不表示文件存在于公开克隆。JSON、diff、源码、原始模型结果和截图不因翻译改写。
