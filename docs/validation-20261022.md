# 2026-10-22 文档中文化验证

本次在独立工作副本中继续更新 PR #1 的 `codex/readme-zh-20261018` 分支，起点为 `6171094c06ad4fd8d7582bd84e72aca915e53052`。原本地仓库的未提交 README 和未跟踪文档保留原状。

## 变更范围

- `README.md`：中文主文档，增加已实现功能、依赖依据、模块关系、源码导读、两种部署模式、验证边界、目录与后续规划。
- `README_EN.md`：保留 `main` 基线 `a93c5483d9ccbc5d8a90e9f95063d303e3ecbc3d` 的原英文 README 正文，仅在顶部增加语言切换链接。
- `docs/deployment-public-demo.md`：将现行部署说明中文化，保留命令、变量、API 与 nginx 配置，补充状态检查和避免覆盖 `.env` 的复制方式。
- `docs/architecture-cheatsheet.md`：修正候选源码转换为 diff 的流程，统一历史测试的版本口径。
- `docs/TEST_EVIDENCE.md`：增加本次验证入口与独立测试步骤。
- 本记录：说明本次验证方法、结果及未覆盖范围。

未修改程序逻辑、依赖、Compose、Dockerfile、测试、录制数据或既有验收清单。历史设计与评测报告保持原文，其旧版本限制由中文首页明确提示。

## 验证结果

| 检查 | 结果 | 范围与方法 |
| --- | --- | --- |
| Markdown 链接与图片 | 103 处引用通过 | 使用 markdown-it-py 4.0.0 解析六个本次变更文件，检查相对路径、图片文件和 Markdown 锚点；localhost 链接不发起请求 |
| Mermaid | 2 个图语法解析通过 | Mermaid 11.12.0，分别解析中文与英文 README；验证工具单独安装，未加入项目依赖 |
| 英文保留与语言切换 | 通过 | 去掉新增语言切换行后，`README_EN.md` 与基线 `main` 的原 README 正文逐字一致；两份首页均有语言链接 |
| 前端现有测试 | 17 passed | `npm test`；包含回放行为、文档标题、文本转义与链接处理 |
| 只读 API 现有测试 | 78 passed，1 warning | `python -m pytest tests/test_portfolio.py -q`，临时目录显式设在工作区；校验录制一致性、变更拒绝、路径与展示边界 |
| Compose 配置 | 两种配置均通过 | 分别执行 `docker compose config --quiet` 和 `docker compose -f compose.live.yaml config --quiet`；使用空的 Docker 客户端配置目录进行静态检查 |
| 变更范围与格式 | 通过 | `git diff --check`，并检查变更清单只有六个文档文件 |
| 凭据与本机路径模式检查 | 未检出 | 检查六个变更文件中的凭据形态、私钥头和本机绝对路径；不声称覆盖所有编码或语义泄露 |
| 原工作区保护 | 8 个文件哈希一致 | 对原未提交 README 和七个未跟踪文档逐文件比较 SHA-256；未向原仓库写入 |

执行环境：Windows、Python 3.13.5、Node v24.14.1、Docker Compose 5.4.0。Python 验证使用独立虚拟环境，最小验证依赖按 README 的固定版本安装，并受 `requirements.lock` 约束；FastAPI 0.115.12、HTTPX 0.28.1、pytest 8.4.1、Pydantic 2.13.5、Starlette 0.46.2。Dockerfile 使用 Python 3.12，本次没有宣称在该容器 Python 版本下重跑。

首次只读 API 测试为 77 passed、1 error：pytest 默认临时目录因 Windows 权限无法访问，最后一个测试未能初始化。随后仅将 `--basetemp` 指向新的工作区目录，完整重跑为 78 passed，未修改断言或跳过测试。两次 JUnit XML 均在独立工作副本外保留。警告为上游 AnyIO `BlockingPortal` 别名弃用提示，不是模型或业务验证结论。

Mermaid 首次直接在无 DOM 的 Node 环境解析时，DOMPurify 初始化失败；补充独立 jsdom 环境后使用原图解析通过，未为绕过验证修改图或程序。依赖下载使用了工作区外层的独立工具目录和缓存。

## 未覆盖范围

本次没有启动 Docker 服务、注入故障、执行完整后端/浏览器 E2E 或调用付费模型，也没有更新冻结 Benchmark。Compose 检查只验证配置可解析，不代表重新构建和启动验证通过。

语言切换和源码链接面向 GitHub 阅读。内置演示文档阅读器沿用现有文件名白名单，未扩展到 `README_EN.md` 或源码文件；需要在 GitHub 查看这些链接。
