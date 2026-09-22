> Historical design note. Current Phase 4 runtime, compiler, generic sandbox and recovery evidence are documented in [phase4-runtime.md](phase4-runtime.md), [phase4-generic-patching.md](phase4-generic-patching.md) and [phase4-recovery-security.md](phase4-recovery-security.md).

# 工作流可靠性与恢复

状态表 `investigation_checkpoints` 保存 run ID、阶段、JSON 状态和更新时间。阶段包括 CREATED、TRIAGE、PLANNING、INVESTIGATING、ROOT_CAUSE、PATCHING、TESTING、VERIFYING、COMPLETED、FAILED。阶段转移也进入 `agent_steps`。

Investigator 在模型调用前、收到工具批次后、每个工具结果写入对话后保存 checkpoint。工具 provider ID 对应审计账本。重启若发生在工具成功提交之后、游标提交之前，恢复会从账本复用工具结果；不会在该窗口内重复执行已成功的观测工具。测试实际使用 PostgreSQL 和 Redis 验证这一点。

API 启动时自动恢复 `started` 的 Hybrid run，V1 保持原来的中断标记。失败的 Hybrid run 可通过 `POST /api/incidents/{id}/resume` 从保存的状态恢复；不会静默创建新 run。每 run 恢复次数最多 3 次，原始失败事件继续保留。429、5xx、网络错误和 timeout 首先由传输层最多重试 3 次；重试耗尽后保存 FAILED checkpoint，后续可以恢复。

这不是分布式 exactly-once 保证：远端模型已处理但响应尚未保存时，重启可能再次请求模型；中断请求的用量未知。阶段级 Patch 恢复也可能再次生成/验证候选。没有多副本分布式租约，当前 API 是单进程拥有 run。旧证据不会因恢复自动变新，应根据采集时间复查。操作员恢复测量复用已有 recovery row，避免重启后插入重复主键。

## 测试证据

- `tests/test_hybrid.py` 验证真实 Redis 观测提交后重新加载 checkpoint，再处理同一工具批次，工具账本仍只有一条记录。
- `evaluation/resume-preflight-failure.json`：真实 Planner 返回了对象数组而非字符串数组，保留原始 schema 失败；随后在系统提示中提供完整 schema。
- `evaluation/resume-live.json` 和 `evaluation/resume-live-after-loop-fix.json`：容器重启后同一 run 和原始证据均保留，但后续调查触发工具预算。不能把它们称为完整通过。
- `evaluation/resume-final.json`：冻结实验前 V3 真实模型/容器重启预检，后续调查预算失败，保留原始结果。
- `evaluation/resume-post-evaluation.json`：最终 V2 健康工作负载上的真实容器重启检验通过。Incident `ca097c01-02c6-4469-be32-e9207bbcb58c` 保持同一 run 和原始 Evidence，存在恢复事件，最终 checkpoint=COMPLETED。它不属于八场景准确率试验，也不覆盖 V3 的失败。

## 后台故障任务的实际缺陷

inventory 的 `exhaust()` 曾因 Redis 启动时 DNS ConnectionError 永久退出，后来 HTTP 健康也不会重建任务，导致首次连接池注入失效。`evaluation/pool-fixture-proof.json` 记录同镜像重启前后占用 0→4、可用连接降至 0 和真实 HTTP 错误。所有正式有效试验完成后，仅为这个循环增加 RedisError 等待一秒重试；取消仍传播，SQL/并发/故障强度没有改变。49 项最终测试包含此恢复回归，原 48 项冻结实验测试另存。

`evaluation/fault-worker-live-smoke.json` 又验证了修复后运行中的服务能够真实占满连接池，停止故障后 HTTP 错误归零。这是执行器的运维回归，没有新 Agent 模型调用，不并入准确率。当前 14 个容器与源码一致性见 `evaluation/delivery-runtime.json`。

聚合 health observer 先请求 `/health`，失败时无法继续获取该服务 pool-stats；因此故障中该字段可能是 unavailable。补测控制脚本直接查询已有 `/pool-stats` 端点保存真实可用连接数。Agent 没有获得控制端的补测真值。

## 验证和修复边界

独立 Critic 会话不继承 Investigator 完整对话。确定性 Verifier 检查证据引用、独立来源、服务与拓扑/引用的一致性、未处理信号、声明的冲突、相关代码、真实测试、真实 HTTP 重放和 Before/After 来源。LLM VERIFIED 且确定性 FAIL 时，最终降为 PARTIALLY_VERIFIED 并记录 disagreement。这只能阻止结构性误放行，不能证明因果语义正确。

Patch 风险根据文件数、修改行数、数据库、并发、基础设施和 API Contract 变化分 LOW/MEDIUM/HIGH。所有 AI Patch 都需要明确操作员 Apply，HIGH 从不自动发布。当前可执行的 Patch 沙箱仍限于 order-service 的 pricing 函数；payment/inventory/通用 order 处理器的安全隔离及不变合同尚未完成。NO_CODE_PATCH 生成 Remediation Plan，不执行任意基础设施命令。

Docker Desktop 启动失败的现场原因和处理记录在开发测试记录中：仅备份重建失效 socket 目录，未重置数据库或容器卷。正式实验期间禁止迁移、重启、并行故障注入或修改业务/评分代码。
