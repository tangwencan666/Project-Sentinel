# 原始事故报告与早期实验：中文阅读索引

[文档导航](index.md) · [历史总索引](history-index.md)

以下 Markdown 含自动导出的模型输出、工具 JSON、测试日志和机器字段，属于原始证据。文件名、正文、数值和结构保持原样；中文说明只帮助选择阅读入口，不冒充重新诊断或评分。

| 原始报告 | 阅读重点 |
| --- | --- |
| [数据库事故](ai-database-incident-report.md) | 查看诊断引用的数据库观测、查询窗口、根因与 Critic 边界；原始机器载荷不翻译 |
| [调用事故](ai-call-incident-report.md) | 查看跨服务调用、Trace、调用账本和模型报告；结合版本和时间，不当作当前实时数据 |
| [代码事故](ai-code-incident-report.md) | 对照源码证据、候选 diff、基线/候选测试与重放；候选通过不代表已部署 |
| [Kafka 失败诊断](ai-kafka-failed-diagnosis-report.md) | 保留错误归因与解释，不能因翻译删去失败或改成成功 |
| [样例事故报告](sample-incident-report.md) | 原导出格式与事件/证据字段，不用作新模型样本 |
| [第三阶段交付](phase3-delivery.md) | 保留历史中文总结、原始载荷和 V3 失败口径 |
| [早期评测](evaluation.md) | 早期方法与冻结结果，当前导航另见 V4.1 与独立审计 |

V3 完成 2/8、根因 1/8，V3.1 首轮完成/根因 1/8，失败保留；后续资格 5/5 不覆盖它们。完整公开回放从 [五分钟演示](demo-5min.md) 进入，不需要启动旧脚本。

报告中的 `evaluation/`、`outputs/`、`artifacts/` 路径可能是未随 Git 分发的本地产物。它们作为原始引用保留，不伪造文件补齐链接。可公开核实的机器记录在 `docs/*.json`、`portfolio/data/` 与 `portfolio/verification.json`，结构、字段和原数据均不翻译。
