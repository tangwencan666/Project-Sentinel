# 测试证据与版本索引

日期：2026-10-18。历史成绩与本次验收分开。源码快照 Commit 只说明报告所在版本；没有执行时源码哈希的历史记录不升级为当前源码验收。

| 日期 / 版本 | 范围与限制 | 原始证据 |
| --- | --- | --- |
| 2026-09-23，初始审计修订 0d3cc795f2bd | 后端287、前端17；不等于当前模型效果验收 | [docs/independent-final-audit.md](../docs/independent-final-audit.md) |
| Frozen V4.1，冻结产物 SHA-256 见审计 | 8/8 workflow、7/8 root；八个 Critic 均 PARTIALLY_VERIFIED | [CLAIMS_MATRIX.md](../CLAIMS_MATRIX.md) |
| 2026-10-18 前一阶段 | Public API 78 passed，离线；本次未重跑 | [docs/PORTFOLIO_VERIFICATION.md](../docs/PORTFOLIO_VERIFICATION.md) |

详细报告文件 SHA-256 与承载快照登记在 [acceptance-20261018.json](acceptance-20261018.json)。测试数字不跨批次相加，Mock/Stub 不计入真实模型样本。

## 2026-10-22 文档中文化验证

本次继续使用 PR #1 的文档分支，检查中文首页、保留的英文首页、部署说明和架构速记。具体环境、命令和执行结果见 [本次验证记录](validation-20261022.md)。这批验证没有启动 Live Lab 或产生真实模型请求。

只读 API 与前端单测无需运行数据库、缓存或消息服务：

```sh
python -m pip install fastapi==0.115.12 httpx==0.28.1 pytest==8.4.1 -c requirements.lock
python -m pytest tests/test_portfolio.py -q
npm test
```

完整后端测试另需 Python 完整依赖与真实本地实验服务；浏览器测试需要 `npm ci` 安装 Playwright，非 Windows 环境还需浏览器。原始命令保留于 [英文首页的验证章节](../README_EN.md#local-verification-no-paid-benchmark)。它们不是启动只读演示的必要步骤，本次没有重跑这些完整验证。
