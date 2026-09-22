> Historical Phase 4 live-lab guide. For the current no-key portfolio, use [5-minute demo](demo-5min.md) and [10-minute demo](demo-10min.md). Current local live commands require compose.live.yaml and explicit LIVE_AI_ENABLED=true; the old default Compose commands below refer to the frozen Phase 4 layout.

# 现场演示 / Phase 4

## 演示前

`docker compose up -d --build` 启动环境，确认六服务健康、Gateway 可访问、通知消费 offset 正在推进且 lag 很低。等待至少 25 秒健康窗口。正式实验运行时不要另行注入、重启或创建调查；实验控制器会临时暂停自动检测。

模型凭据只在 `.env` 设置，不在屏幕展示。费用无配置单价时显示 Unknown。较长调查宜通过 API 将单次故障 TTL 设置为 600 秒；Fault Lab 按钮默认 120 秒，不能保证故障覆盖较慢模型的全过程。

## 先展示证据与失败

打开 [AI Evaluation](http://localhost:18082/evaluation.html)。六个历史版本的 Workflow 与 Root Accuracy 分别展示：V3 为 2/8 与 1/8，V3.1 首轮为 1/8 与 1/8。后续 5/5 qualification 不替代首轮。V4 两项混杂案例有标记，原分保留并排除 Pareto。

点击单元格查看真实预测、评分、工具与证据。GROUND TRUTH / EVALUATOR ONLY 只属于操作员评估界面。点击播放可浏览阶段事件；RECORDED RUN 明确可见，不调用模型。Conditional Accuracy 要结合完成数看，不能把 1/1 宣传成八场景 100%。

发布 V4.1 位于独立 Benchmark V2 区域。业务结构和可读代码范围已经变化，因此不把它当作单独压缩变量实验。

## Live Investigation

1. Dashboard 选择 **RUNTIME V4.1**。默认 V2 是历史基线操作模式。
2. Fault Lab 触发一个真实故障；等待约 24 秒收集日志、Metrics 与完整 Trace，再创建调查。
3. 展示 TRIAGE、PLANNER、TOOL、EVIDENCE、HYPOTHESIS、ERROR、REPAIR、ROOT CAUSE、PATCH、TEST、CRITIC 阶段。输入中不要附带 scenario_id 或真值。
4. 打开 Runtime Diagnostics：查看 P0 错误、P1 假设与关键证据、六类预算、Context rebuild、Schema repair、Resume、实际 Provider input/output 与 finish reason。
5. 对照 Raw / Compiled 字符数与 Pinned 字符数。字符压缩比例不等于完整模型输入 token 减少，也不证明诊断正确。
6. pricing 代码异常适合展示完整候选链路：模型生成源码、统一 diff、不变测试、三个隔离 HTTP 进程及真实 DB/Redis/Kafka 的前后结果。
7. 候选可以导出 Diff。通用候选没有 live Apply；HIGH 风险财务逻辑必须代码审查与独立发布。PARTIALLY_VERIFIED 不等于 VERIFIED，VERIFIED 也不等于已部署。
8. Infra / Config 事故输出人工 Remediation Plan。停止注入和恢复窗口由操作员执行，不计 AI 修复。
9. 导出 Report，展示证据 ID、实际测试、作用范围与未解决问题。

## 真实恢复证据

`evaluation/phase4/crash-resume-first.json` 保留首次失败：SIGKILL 后状态一致，但工作流因语义提交失败终止。`crash-resume-followup.json` 保存修订后同一 run 完成的复验，包含 exit 137、完整状态指纹、一次 resume 和真实模型用量。测试控制器产生的 missing-symbol 错误有独立来源标签，不能归咎为模型幻觉。

不要为了现场效果对冻结基准点击重新调查或重复选择最好的结果。需要新演示时创建新 Incident；重新运行恢复/注入探测需使用新输出名称，真实模型费用会计入开发用量。

## 必须说明的工程边界

四类候选只覆盖受限业务函数，不支持任意仓库、多文件或数据库迁移修复。沙箱有真实三个服务及依赖，但不是完整六服务克隆或恶意 Python VM。未知价格、缺失观测和旧版本没有保存的诊断显示 Unknown。API 仅限本机，尚无多租户鉴权、分布式执行租约和生产 SLO。八场景单次成绩不能证明统计泛化。
