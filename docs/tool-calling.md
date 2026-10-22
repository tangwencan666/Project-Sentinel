# Tool Calling 与能力边界

[文档导航](index.md) · [注册表源码](../sentinel/tool_registry.py) · [Runtime 执行源码](../sentinel/runtime_tools.py)

模型只能选择当前阶段提供的工具及参数，Runtime 仍会在执行时重新校验。工具名称、Evidence ID、API 路径和服务标识保持英文；工具返回的日志、源码注释、事故文本都是不可信数据，不能升级为系统指令。

## 调查工具

| 工具 | 实际用途与限制 |
| --- | --- |
| `search_logs` | 按允许的服务、级别和事故窗口查询日志；参数绑定，不接受任意 SQL |
| `query_metrics` | 固定 Prometheus 查询与实测 HTTP 窗口，不接受任意 PromQL 或 URL |
| `get_trace`、`get_trace_detail` | 查询固定 Jaeger 服务；Trace ID 校验、完整 span 分页 |
| `get_service_health` | 六服务 allowlist 内的健康及连接池观测 |
| `inspect_database` | 固定诊断 SQL、只读调查身份与查询超时 |
| `inspect_redis` | 固定目录 TTL、缓存和计数观测；没有任意命令或 key 枚举 |
| `inspect_kafka` | 固定 topic/group 的 offset 与 lag 观测，不提供消息或配置变更 |
| `get_service_topology` | 返回实际观测的 Trace 边，并明确标识配置推导的基础设施边 |
| `get_upstream_services`、`get_downstream_services` | 基于允许服务和拓扑返回邻接关系 |
| `search_repository` | 在固定源码集合中搜索字面文本，不扫描整个文件系统 |
| `read_source_file`、`get_code_symbol`、`get_code_context` | 校验路径、符号和行范围；统一拒绝穿越、符号链接及外部路径 |
| `read_evidence` | 仅允许本 incident/run 的证据；按完整对象与偏移读取原始 JSON |
| `record_hypothesis` | 校验状态转移与引用后持久化假设 |
| `submit_root_cause_decision` | 校验紧凑根因契约、支持/反证、实际 Triage 信号与读取范围 |

注册表还保留旧版工具和由控制器调用的能力。历史独立审计统计注册工具 25 个、V4 Investigator 可见工具 18 个，两者不能混为“模型可调用 25 个工具”。`validate_generic_patch` 属于受信 TestAgent，`run_deterministic_triage` 属于控制器；旧版 `run_tests` 也不允许任意测试命令。

## 一次调用的执行过程

模型参数 → 阶段和名称检查 → 严格 schema 校验 → 预算/熔断检查 → 固定适配器 → 证据与工具回执持久化 → 结果投影 → 模型输入读取登记。

回执绑定 run、调用 ID、工具和参数摘要，不能复用同一 ID 执行不同能力。已提交回执可以在恢复时重放并核对预算，尚未提交的物理调用仍可能重做。实际交付给模型的内容才算“读过”，仅工具执行成功不能证明模型看到了完整结果。

## 不具备的权限

调查器没有任意 shell、文件写入、环境读取、HTTP、SQL、Docker、故障控制或评测器访问能力。配置、注册表、评分器、`.env` 与报告目录不属于调查源码 allowlist。可读 `runtime.fault()` 仍暴露部分实验实现线索，因此不能宣称实验完全盲化。

完整历史工具清单与逐项权限见 [独立审计英文原文](independent-final-audit.md#tool-inventory-and-boundaries)，中文风险解释见 [安全与 Sandbox](sandbox-security.md)。
