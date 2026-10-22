# 全仓库中文化扫描与处理清单

[统一导航](index.md) · [历史索引](history-index.md) · [本轮验证](localization-validation.md)

## 扫描基线

基线提交 `53d4fbd`，受 Git 管理的文件 551 个：Markdown 56 份、JSON 312 个、PNG 截图 8 个。Markdown 中按去除代码块/行内代码后英文单词数多于汉字数的可复核口径，英文主导 24 份、中文或中英说明 32 份；此启发式包含技术术语，不代表翻译质量评分。

界面范围：10 个 HTML 入口（九个录制页面和一个本地 Live 页面），5 个显示文本 JavaScript 文件；`replay.js` 是回放逻辑，保持不变。静态标签、说明、按钮、表格、空态和错误提示纳入中文化；模型正文、工具载荷、机器状态码和原始测试日志按原文展示，并提供中文标签/导读。

未发现 `.github/` Issue/PR 模板、CONTRIBUTING 或 CODE_OF_CONDUCT，不为翻译新增不存在的模板。Python 注释、Prompt、API 错误协议、配置和机器数据不属于界面文案，不批量替换。

## 基线 Markdown 逐文件处理

| 文件 | 基线语言 | 类别 | 处理方式 |
| --- | --- | --- | --- |
| [CLAIMS_MATRIX.md](../CLAIMS_MATRIX.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [FINAL_STATUS.md](../FINAL_STATUS.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [README.md](../README.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [README_EN.md](../README_EN.md) | 英文主导 | 英文版本/归档 | 保留原文；中文导读见历史索引 |
| [docs/LOCAL_ACCEPTANCE.md](LOCAL_ACCEPTANCE.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/PORTFOLIO_VERIFICATION.md](PORTFOLIO_VERIFICATION.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/TEST_EVIDENCE.md](TEST_EVIDENCE.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/adversarial-audit.md](adversarial-audit.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/agent-design.md](agent-design.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/ai-call-incident-report.md](ai-call-incident-report.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/ai-code-incident-report.md](ai-code-incident-report.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/ai-database-incident-report.md](ai-database-incident-report.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/ai-kafka-failed-diagnosis-report.md](ai-kafka-failed-diagnosis-report.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/architecture-cheatsheet.md](architecture-cheatsheet.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/architecture.md](architecture.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/context-engineering.md](context-engineering.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/demo-10min.md](demo-10min.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/demo-5min.md](demo-5min.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/demo-guide.md](demo-guide.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/deployment-public-demo.md](deployment-public-demo.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/evaluation.md](evaluation.md) | 中文或中英说明 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/final-portfolio-audit.md](final-portfolio-audit.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/future-work.md](future-work.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/history/README.before-portfolio-20261018.md](history/README.before-portfolio-20261018.md) | 英文主导 | 英文版本/归档 | 保留原文；中文导读见历史索引 |
| [docs/hostile-audit.md](hostile-audit.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/independent-final-audit.md](independent-final-audit.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/interview-depth-map.md](interview-depth-map.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/interview-hard-questions.md](interview-hard-questions.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/interview-qa.md](interview-qa.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/limitations.md](limitations.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/phase3-delivery.md](phase3-delivery.md) | 中文或中英说明 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/phase3-failure-analysis.md](phase3-failure-analysis.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/phase4-adversarial-audit.md](phase4-adversarial-audit.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/phase4-delivery.md](phase4-delivery.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/phase4-evaluation.md](phase4-evaluation.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/phase4-followup-findings.md](phase4-followup-findings.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/phase4-generic-patching.md](phase4-generic-patching.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/phase4-recovery-security.md](phase4-recovery-security.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/phase4-runtime.md](phase4-runtime.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/phase4-v4-methodology.md](phase4-v4-methodology.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/phase5-acceptance.md](phase5-acceptance.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/phase5-adversarial-audit.md](phase5-adversarial-audit.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/phase5-handoff.md](phase5-handoff.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/pitch-1min.md](pitch-1min.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/pitch-30s.md](pitch-30s.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/pitch-3min.md](pitch-3min.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/project-pitch.md](project-pitch.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/reliability.md](reliability.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/resume-short.md](resume-short.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/resume.md](resume.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/sample-incident-report.md](sample-incident-report.md) | 英文主导 | 原始报告/历史证据 | 保留原文；中文导读见历史索引 |
| [docs/status.md](status.md) | 英文主导 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/tech-stack.md](tech-stack.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/v1-failure-analysis.md](v1-failure-analysis.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/v3-failure-story.md](v3-failure-story.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |
| [docs/validation-20261022.md](validation-20261022.md) | 中文或中英说明 | 正式说明/中文材料 | 中文主文或中文材料；补充英文标题/图示和版本说明 |

## 保留英文的理由

基线 25 份 Markdown 原件按哈希保持不变，包括英文 README/归档、独立审计/声明矩阵/阶段报告、自动导出报告和含大量原始载荷的早期评测。每份均有中文导航或导读。`docs/resume.md` 的英文简历正文也保留，用于英文投递。312 个 JSON、已有 diff、截图、锁文件、程序协议和标识符不翻译；日志与模型文本仍可从原始证据核验。

本次新增文件与完整变更清单由 [本轮验证记录](localization-validation.md) 说明。

## 界面英文候选扫描

基线 HTML 提取静态文字、title/aria-label/placeholder/description；JavaScript 用 Acorn 解析字面量和模板片段，再提取可见 HTML 文字或英文标签。候选包含技术标识和少量控制文本，按出现次数统计，不等于必须翻译的独立文案数；动态原始模型/JSON 内容另归证据类保留。

| 显示文件 | 基线英文候选片段 |
| --- | --- |
| `web/app.js` | 94 |
| `web/architecture.html` | 5 |
| `web/documentation.html` | 5 |
| `web/documents.js` | 5 |
| `web/evaluation.html` | 5 |
| `web/evaluation.js` | 74 |
| `web/evidence.html` | 5 |
| `web/incident.html` | 5 |
| `web/index.html` | 5 |
| `web/live.html` | 78 |
| `web/patch.html` | 5 |
| `web/portfolio.js` | 337 |
| `web/replay.html` | 5 |
| `web/root-cause.html` | 5 |
| `web/runtime.js` | 48 |

合计 681 个候选片段。界面路由、数据结构及标识不据此批量翻译，最终以真实交互测试和原件哈希核验。
