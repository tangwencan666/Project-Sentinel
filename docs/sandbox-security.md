# Sandbox、候选验证与安全边界

[文档导航](index.md) · [候选校验源码](../sentinel/generic_patching.py) · [多服务 Sandbox](../sentinel/multiservice_sandbox.py)

## 支持的候选范围

| 文件 | 允许替换的业务函数 |
| --- | --- |
| `services/pricing.py` | `total` |
| `services/payment.py` | `normalize_amount` |
| `services/order.py` | `choose_item` |
| `services/inventory.py` | `normalize_product` |

模型提交完整替换源码，控制器对照实际基线计算 Unified Diff，不修改模型逻辑。每个候选仅能修改一个允许文件，签名、默认值和返回注解保持一致。AST 限制拒绝 import、属性访问、循环、嵌套函数、私有名字与任意调用；测试、真值、基础设施和密钥路径不允许修改。

## 验证链路

基线与候选分别执行不可变合同测试，再启动 order、inventory、payment 三个 HTTP 进程进行相同输入重放。可信包装层访问真实 PostgreSQL、Redis 和 Kafka；每次重放使用独立 schema、key namespace 与 topic。候选纯函数本身无 I/O 能力，Worker 没有模型密钥。

健康对照要求结账成功、写入业务行并观察 Kafka 事件。输入被拒绝可能增加 4xx/503，所以业务违例率、HTTP 5xx、P95 和健康对照分别报告，不能将“拒绝请求”宣传为性能优化。

四类模型组件候选在历史后续实验中通过 4/4，早先 diff 格式尝试仅通过 2/4，失败均保留。这是组件验证，不是端到端根因准确率。冻结 V4.1 定价候选通过 9 项合同测试；相同八个错误输入的 HTTP 500 从 100% 变为 0%，P95 却从 55.83 增至 98.68 ms，候选仍未部署。

## 风险与权限

财务逻辑为 HIGH risk；通用候选 `automatic_apply_allowed=false`，不能使用旧版定价覆盖入口部署。配置与基础设施建议保持人工操作，不执行任意运维命令。

非 root、CPU/内存/文件限制和独立依赖命名空间有助于约束受限函数，但 Worker 共享容器内核及基础设施，且实验数据库身份权限较大。这里不是任意恶意 Python 的 VM、多租户隔离或生产发布系统。中途强制终止可能遗留临时命名空间。

## 公开模式与 Live 模式

公开镜像只含录制读取能力，拒绝非 GET/HEAD 请求，限制 Host、CSP 和文件路径，并在启动时验证 manifest。它没有模型、数据库、故障注入或 Apply 能力。Live Lab 默认关闭变更控制，仍缺生产级鉴权、RBAC、分布式租约和发布审批，不能直接对公网开放。

独立审计修复了必需证据交接、符号链接读取、Range 解析入口及 Host 路径门禁；依赖维护、共享内核、事务一致性和许可缺失仍有未解决项。历史四次真实模型注入探测未越权，只是有限样本，不能证明普遍免疫。

详见 [独立审计中文导读](independent-final-audit-zh.md)、[原始声明矩阵中文导读](claims-matrix-zh.md) 和 [部署说明](deployment-public-demo.md)。
