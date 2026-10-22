# Runtime 恢复与信任边界：中文导读

[文档导航](index.md) · [英文原始记录](phase4-recovery-security.md) · [当前 Checkpoint 说明](evidence-checkpoint.md)

阶段 H 扩展合格 Runtime，不替换正式 RCA 结果。历史门禁分别保留 169、183、185 项等记录，不跨批次相加。

## 持久化契约

Provider 请求绑定 run/stage/attempt 逻辑键，以及精确脱敏消息、工具与 tool choice 摘要。公开响应、Tool Calling、用量和诊断共同提交；恢复时只复用匹配请求，隐藏推理字段不存储。模型实际输入的读取登记持久化，不追认未交付证据。

schema 修复按尝试计费，工具回执核对预算；已完成候选验证保留失败反馈和尝试键。完成但未提交的沙箱验证仍可能重复，远端响应落盘前丢失也可能再次计费，不承诺所有物理工作 exactly-once。

## 真实进程恢复实验

`RecoveryTestController` 在真实 Investigator 已形成假设与关键证据后，注入一次实际不存在的符号调用，来源单独标注。主机 SIGKILL 指定一次性容器，检查 exit 137，启动新 Worker，对比完整状态指纹再恢复相同 run。

首次精确恢复快照后，三次语义提交仍保留矛盾证据，最终失败，消耗 191,054 Token。诊断发现结账调用方不可读，以及拒绝逻辑不允许继续读取矛盾证据。尝试直接放开混合业务/故障的 `services/app.py` 时，旧安全测试拒绝，门禁为 183 passed、2 failed；没有删除测试。

后续抽取不含实验控制的 `services/checkout.py`，保留三次提交、两次 schema 修复上限，返回 `UNRESOLVED_CONTRADICTION` 及有界纠错能力。185 项门禁后，同一 run 恢复完成：一次 resume、12 次 DeepSeek 调用、136,881 Token，定价候选通过三服务 Sandbox；Critic 仍为 `PARTIALLY_VERIFIED`，未部署。

## 协议与攻击 fixture

429/500 使用真实本机 HTTP 服务和 PostgreSQL Checkpoint；无效 JSON 修复落盘后重新加载，验证不重复请求/扣预算。慢端点用 20 ms 加速测试，实际工具 deadline 仍为 25 秒。合同失败与修复在真实依赖 Sandbox 验证，均不计入模型准确率。

Runtime dispatcher 测试路径穿越、密钥路径、shell/SQL 注入、超大参数、任意 HTTP 和角色提权。四次真实 DeepSeek 注入探测涵盖日志、源码注释、事故和 Trace，合计 17,183 Token，均选择安全能力；恶意文本是标注 fixture，不能推广为注入免疫。

候选进程共享内核、依赖服务器和实验身份。notification consumer 有监督及有界重连，启动/消费失败反映为 HTTP 503；故意积压与死任务分别测量。业务抽取与 readiness 变化需新版本 Benchmark，不回写旧结果。
