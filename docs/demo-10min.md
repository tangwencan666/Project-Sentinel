# 10 分钟技术演示

使用默认只读 Demo，不调用 DeepSeek。先按 demo-5min.md 熟悉操作。

## 0:00–1:00 · 定位与真实边界

介绍 Project Sentinel：AI-Powered Production Incident Investigation & Remediation Platform。展示录制模式、同一 Run ID 和真实时间。区分 investigation completion、RCA accuracy、candidate verification 和 production deployment。

## 1:00–2:00 · Architecture

打开 Architecture：Dashboard → Incident API → Agent Runtime → Tools → 六服务。说明实验业务流量、SQL、缓存、消息和 Trace 的关系；公网只读 Demo 本身不运行这些实验依赖。

## 2:00–3:30 · Runtime / Replay

1× 播放几秒，展示工具、错误，再切 4×。暂停一次 ERROR，查看原始错误里的 expected、actual 和 suggested_action。

讲解 typed InvestigationState、P0/P1 pinned state、假设状态机、citation read registry、六类独立预算、最多两次结构化修复、重复失败熔断。Checkpoint 保存未完成动作；响应 journal 和 tool receipt 复用已提交结果，但不保证远端请求计费 exactly-once。

## 3:30–4:30 · Context engineering

Evidence 页默认 summary，点开 raw 才下载原证据。解释运行期 Evidence Compiler 处理日志聚类、指标窗口、Trace 和代码；字符压缩比不能当作 token 节省或正确率证明。

坦诚指出：Investigator 的引用已读检查并不保证 Critic 收到每条引用。最终失败案例中一条代码证据被 Critic packet 淘汰，这是开放问题。

## 4:30–6:00 · Root Cause 与 Patch

看 pricing.py 的 None discount 根因；打开代码引用。展示真实 diff、baseline 失败、candidate 9 passed、三服务八请求前后结果。专用 DB schema、Redis namespace、Kafka topic 是逻辑隔离；进程仍共享内核。通用候选不自动 Apply，HIGH 风险财务代码必须审查后独立发布。

## 6:00–7:30 · Benchmark 与 Ground Truth

Evaluation 页展示所有版本。说明 Scenario Registry 和 Evaluator 不在调查工具权限内；Ground Truth 用于工作流结束后的评分。代码中可见的 generic fault helper 仍暴露实验实现，因此不能称为完全盲测。

解释 V3 2/8、V3.1 首轮 1/8、后续资格验证 5/5、V4 混杂案例及独立 benchmark-v2 的 V4.1 7/8。不可跨环境变化作单变量因果比较，不用失败提前结束造成的低 tokens 宣传优化。

## 7:30–8:30 · Recovery / Security

展示 Documentation → All engineering & interview documents → Phase 4 security & limits：实际 kill / exit 137 / 同 run resume 证据，以及首次恢复后仍失败的保留记录。Provider 429/500、非法 JSON 和 timeout 用本地协议服务器测试；不能说都是真实云 Provider 故障。

公网镜像只有只读文件 API；没有凭据、DB client、LLM provider 或 tool dispatcher。写路由统一拒绝，本地 Live 另外 opt-in。Prompt Injection 防线是能力边界、数据不可信和受限 Patch AST，不是“提示词保证安全”。

## 8:30–9:30 · Trade-offs

约 1.46M tokens / 八场景，106 次模型调用。不是低成本答案生成器。缓存已提交响应降低重复工作，但不能修复丢失提交前的远端响应。Rule 在固定领域里很有效；LLM 的源码关联和自然语言推理能力需要更多不同事故验证。

## 9:30–10:00 · 下一步

优先修复 Critic 的必需引用传递；隔离实验控制代码；增加分布式执行租约、鉴权与配额、独立模型复核和真实生产样本。下一步不是刷出 100% Benchmark。结束时再说明所有页面是实际历史数据回放，未调用模型。
