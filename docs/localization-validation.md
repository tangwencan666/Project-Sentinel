# 全仓库中文化验证与交付记录

[统一中文导航](index.md) · [扫描清单](localization-inventory.md) · [历史原件索引](history-index.md)

工作基线为 PR #1 的 `53d4fbd`，继续使用 `codex/readme-zh-20261018` 独立副本。原本地 `main` 的未提交 README 与七份未跟踪文档保持原状。

## 范围

正式文档补齐中文导航、Runtime、Tool Calling、Evidence/Checkpoint、Sandbox 安全与测试说明；历史英文报告逐篇提供中文导读，原件保持字节一致。界面翻译只作用于显示文本、中文导读和必要文档链接，控制键、枚举、事件绑定及原始机器数据保留。

## 执行结果

| 检查 | 本轮实际结果 | 说明 |
| --- | --- | --- |
| 全仓库 Markdown | 82 份，489 处相对引用通过 | 包含链接、图片与 Markdown 锚点；外部历史公告/localhost 不作联网可用性认证 |
| Mermaid | 6 个图解析通过 | Mermaid 11.12.0 + 独立 jsdom 工具环境，不修改项目依赖 |
| 前端单测 | 18 passed | 现有 17 项加一项大写文档链接/路径边界回归 |
| 相关后端 | 78 passed，1 warning | `tests/test_portfolio.py`；原始录制、公开边界、来源与下载，无真实模型 |
| 真实录制浏览器 | 37 checks passed | 九页面、三视口、56 个历史按钮、文档、筛选、懒加载、播放/暂停/倍速及错误/空态 fixture；零脚本/资源错误与变更请求 |
| 中文演示干跑 | 8 步通过 | 实际浏览器按五分钟指南操作，不测量人类口述用时，零外部请求/变更请求 |
| 本地 Live 前端 | 6 项 fixture 检查通过 | 标注的前端响应 fixture；导航/禁用状态与零变更，不是启动真实 Lab |
| DOM/控制标识 | 155 个绑定属性、126 个选择器保持一致 | 对照基线；阶段分类、事件样式、动画三处控制函数与 `replay.js` 保持不变 |
| 原件保护 | 25 份 Markdown、共 486 个受保护文件字节一致 | JSON、Python、已有 diff/PNG、锁文件、Compose/SQL/Dockerfile、回放逻辑及历史原件 |
| 原工作区 | 8 个文件 SHA-256 保持一致 | 原未提交 README 与七份未跟踪文档，原分支与未提交工作保留 |
| Compose/格式 | 两种 Compose 静态配置、`git diff --check` 通过 | 不构建、不启动完整实验环境 |
| 敏感与路径模式 | 变更文本未检出 | 凭据形态、私钥头与本机绝对路径；不声称覆盖所有编码泄露 |

环境：Windows、Python 3.13.5、Node v24.14.1、Docker Compose 5.4.0、Edge/Playwright 1.62.1。API 验证虚拟环境使用 FastAPI 0.115.12、HTTPX 0.28.1、pytest 8.4.1、Pydantic 2.13.5、Starlette 0.46.2，受原 `requirements.lock` 约束。未在 Dockerfile 的 Python 3.12 容器中重跑。

前端与静态命令：`npm test`、`docker compose config --quiet`、`docker compose -f compose.live.yaml config --quiet`、`git diff --check`。后端执行 `python -m pytest tests/test_portfolio.py -q`，附新的工作区 `--basetemp` 与 JUnit 路径。浏览器执行 `scripts/test_portfolio_browser.cjs`、`scripts/test_interview_demo.cjs`，指向独立回环只读服务与新结果名；结果不覆盖旧文件。Playwright/Mermaid/扫描器安装在仓库外层独立验证目录。

首次真实浏览器尝试因 Windows 注册的 `.js` MIME 为 `text/plain` 被严格类型检查阻止，未形成通过记录。只在独立测试启动器中调用 `mimetypes.add_type('text/javascript', '.js')` 后重跑；未为此修改服务源码。后续第二轮和最终轮均 37 项通过，原失败报告保留。上游 AnyIO `BlockingPortal` 弃用警告保留，不升级依赖绕过。

## 结果工件摘要

完整原始日志、报告与新截图保留在本轮独立副本的忽略目录或外层验证目录，不发布含本机路径的原日志。以下 SHA-256 用于核对本次会话产物，不是第三方签名：

| 工件 | SHA-256 |
| --- | --- |
| `sentinel-full-l10n-public.xml` | `517a9d4482eea9f40a0bc97c97d83b503d8c79abe16d4aa4b1d783c952dbca90` |
| `browser-localization-20261022-first.json`（MIME 失败） | `341278114c3b8d8f4228261fff0b8b84de6fc972083440c4d0ac21b9f5fe9125` |
| `browser-localization-20261022-final.json` | `0c442a509557670b9c8b9a7cc3a5cb08ca386be5907edf14dd15d231ebbb1dcc` |
| `demo-localization-20261022-first.json` | `d4da9ce054917a4f3364ad509227b5297f1b33de3c168fee56310355da4a9492` |
| `sentinel-live-frontend-fixture.json` | `42b3a2f107773a9909eb23025b032633196f792d9c82db819ace2582ad4a44b3` |

## 完整变更清单

共 60 个文件：42 份 Markdown、10 个 HTML、5 个显示 JavaScript、2 个浏览器验证脚本、1 个文档测试。新增 26 份中文文档包括 5 份工程说明、17 份历史导读及 4 份导航/扫描/验证记录；其余为现行材料与显示文本的一致性更新。未修改 Python、数据库、依赖、锁文件或部署配置。

```text
README.md
docs/TEST_EVIDENCE.md
docs/agent-design.md
docs/agent-runtime.md
docs/architecture-cheatsheet.md
docs/architecture.md
docs/claims-matrix-zh.md
docs/context-engineering.md
docs/demo-10min.md
docs/demo-5min.md
docs/demo-guide.md
docs/evidence-checkpoint.md
docs/final-portfolio-audit-zh.md
docs/final-status-zh.md
docs/future-work.md
docs/history-index.md
docs/hostile-audit-zh.md
docs/incident-reports-zh.md
docs/independent-final-audit-zh.md
docs/index.md
docs/interview-hard-questions.md
docs/interview-qa.md
docs/localization-inventory.md
docs/localization-validation.md
docs/phase4-adversarial-audit-zh.md
docs/phase4-delivery-zh.md
docs/phase4-evaluation-zh.md
docs/phase4-followup-findings-zh.md
docs/phase4-generic-patching-zh.md
docs/phase4-recovery-security-zh.md
docs/phase4-runtime-zh.md
docs/phase4-v4-methodology-zh.md
docs/phase5-acceptance-zh.md
docs/phase5-adversarial-audit-zh.md
docs/phase5-handoff-zh.md
docs/reliability.md
docs/resume-short.md
docs/resume.md
docs/sandbox-security.md
docs/status.md
docs/testing.md
docs/tool-calling.md
scripts/test_interview_demo.cjs
scripts/test_portfolio_browser.cjs
tests/documents.test.cjs
web/app.js
web/architecture.html
web/documentation.html
web/documents.js
web/evaluation.html
web/evaluation.js
web/evidence.html
web/incident.html
web/index.html
web/live.html
web/patch.html
web/portfolio.js
web/replay.html
web/root-cause.html
web/runtime.js
```

## 未执行与限制

不调用真实模型、付费 API，不注入故障、不运行生产环境、不重跑冻结 Benchmark。浏览器仅访问本轮独立只读服务，Live 页面用标注的只读 fixture 验证显示与禁用状态。历史 PNG 不覆写，新截图单独保留。

英文 README、原始模型结果、事件载荷、测试日志及历史报告保留英文以维持可核查性；中文导读不构成新模型结论。历史原文中的旧端口、pricing 单路径、测试数量和发布前状态以版本导读解释，不回写原件。
