# 测试、验证与结果口径

[文档导航](index.md) · [历史证据索引](TEST_EVIDENCE.md) · [中文化验证](localization-validation.md)

## 无需模型的本地验证

在新的虚拟环境中安装最小依赖；完整依赖以仓库锁文件为约束，不修改锁文件：

```sh
python -m pip install fastapi==0.115.12 httpx==0.28.1 pytest==8.4.1 -c requirements.lock
python -m pytest tests/test_portfolio.py -q
npm test
docker compose config --quiet
docker compose -f compose.live.yaml config --quiet
git diff --check
```

只读 API 测试校验录制来源、路径、变更拒绝与展示边界，Node 测试校验回放和 Markdown 阅读器；它们不需要启动 Live Lab。Windows 临时目录受限时，为 pytest 指定一个新的工作区 `--basetemp` 目录，保留已有报告，不删除旧结果。

## 浏览器与完整后端

浏览器测试需要 Node、Playwright 和真实浏览器；只启动只读演示即可。测试应检查九个页面、中文导航、播放/暂停/倍速、证据懒加载、候选禁用状态、历史结果与文档导航，并监听非 GET/HEAD 请求，避免意外进入 Live 操作。历史截图和报告保留，不为翻译覆盖旧证据。

完整后端使用 `python -m pip install -r requirements.txt -c requirements.lock`，部分测试依赖真实 PostgreSQL、Redis、Kafka 和 Linux 资源限制。`scripts/test_phase5.py` 是历史完整环境入口，不能把其旧报告作为本次执行结果。新的模型评测、故障注入、进程 kill 或生产验证需单独说明范围并取得授权，本轮不执行。

## 如何引用结果

| 记录 | 正确表述 |
| --- | --- |
| 冻结 V4.1 | 8/8 工作流、7/8 根因/服务定位，八场均为 `PARTIALLY_VERIFIED` |
| 189 passed | 冻结 Benchmark 当时的测试门禁 |
| 267 后端、17 前端 | 历史 Phase 5 批次 |
| 287 后端、17 前端 | 历史独立审计批次 |
| 浏览器与 HTTP 检查 | 独立验证类别，不加到单元测试数或模型样本数中 |
| 当前中文化验证 | 只引用 [本轮记录](localization-validation.md) 中实际执行的命令、结果与环境 |

历史 V3/V3.1 失败、V4 混杂试验、恢复与组件实验均独立保留。资格验证 5/5 不替换 V3.1 首轮 1/8；修复当前引用保护后也不自动继承冻结版本的完成率。
