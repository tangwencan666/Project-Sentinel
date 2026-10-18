# 测试证据与版本索引

日期：2026-10-18。历史成绩与本次验收分开。源码快照 Commit 只说明报告所在版本；没有执行时源码哈希的历史记录不升级为当前源码验收。

| 日期 / 版本 | 范围与限制 | 原始证据 |
| --- | --- | --- |
| 2026-09-23，初始审计修订 0d3cc795f2bd | 后端287、前端17；不等于当前模型效果验收 | [docs/independent-final-audit.md](../docs/independent-final-audit.md) |
| Frozen V4.1，冻结产物 SHA-256 见审计 | 8/8 workflow、7/8 root；八个 Critic 均 PARTIALLY_VERIFIED | [CLAIMS_MATRIX.md](../CLAIMS_MATRIX.md) |
| 2026-10-18 前一阶段 | Public API 78 passed，离线；本次未重跑 | [docs/PORTFOLIO_VERIFICATION.md](../docs/PORTFOLIO_VERIFICATION.md) |

详细报告文件 SHA-256 与承载快照登记在 [acceptance-20261018.json](acceptance-20261018.json)。测试数字不跨批次相加，Mock/Stub 不计入真实模型样本。
