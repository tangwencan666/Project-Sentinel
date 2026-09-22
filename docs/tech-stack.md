# 实际技术栈

仅列仓库、依赖和运行配置中实际使用的技术。版本以依赖锁文件与 Compose 为准。

| 层 | 实际使用 | 作用与范围 |
|---|---|---|
| Frontend | 原生 HTML、CSS、JavaScript、SVG | Dashboard、回放、拓扑、文档阅读器；没有 React/Vue、前端构建服务器或 CDN 依赖。 |
| Backend | Python 3.12、FastAPI、Uvicorn、Pydantic、HTTPX、asyncio | 六服务与 Incident API、工具参数和结构化结果校验、自建 Agent Runtime。 |
| Infrastructure | Docker Compose、PostgreSQL、psycopg/pool、Redis、Redpanda、aiokafka | 真实 SQL、连接池、缓存、Kafka 兼容生产/消费；不是 Kubernetes 部署。 |
| Observability | OpenTelemetry SDK/instrumentation、OTLP Collector、Jaeger、Prometheus、结构化日志 | 跨服务 Trace、指标和日志；调查工具读取真实数据，公开模式读取冻结投影。 |
| AI | deepseek-chat、兼容 Chat Completions 的 HTTP 协议、自建 Hybrid/Runtime、AST 源码工具 | 真实工具调用、证据引用、根因、受限候选及 Critic；没有模型训练、向量数据库或已实施 RAG。 |
| Testing | pytest、Node 内置 test runner、Playwright/Edge 或 Chromium | 后端/协议/沙箱测试，回放和文档单测，真实浏览器 E2E；本地 provider fixture 与真实云 benchmark 分开。 |
| Security | 工具/路径 allowlist、参数与 AST 校验、非 root 进程、容器只读文件系统、CSP、Host allowlist、密钥脱敏 | 公开镜像无 provider/DB/tool 模块及密钥。不能据此声称 Live 系统具备完整生产 RBAC 或强沙箱隔离。 |

默认 `compose.yaml` 仅启动录制前端、只读 API 与文件数据；完整微服务与可观测环境在 `compose.live.yaml`。Node/Playwright 仅用于开发验证，演示运行不需要 Node。
