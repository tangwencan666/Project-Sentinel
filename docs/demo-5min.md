# 五分钟 Demo · 点击、观察、讲解

准备：运行 `docker compose up -d --build`，打开 http://localhost:18082，窗口建议 1366×768 或以上。整个演示使用 RECORDED DEMO，不填写 Key，不打开 Live，不触发故障，不重新评估。

下面时间是口述预算。括号中的名称是界面实际英文按钮；没有逐字念长 ID 或原始日志的必要。

## 00:00–00:30 · Dashboard

**点击哪里：**左侧 Overview。

**页面出现什么：**项目定位、RECORDED DEMO、六服务拓扑，以及 V4.1 的 8/8 workflow、7/8 RCA。

**应该说什么：**“结账出错时，Sentinel 让 AI 查真实日志、指标和源码，以证据定位原因，再在沙箱测试修复候选。这里是一次真实调查的回放，页面错误率属于历史窗口。”

## 00:30–01:00 · Architecture

**点击哪里：**左侧 Architecture，稍向下滚动至 Runtime architecture。

**页面出现什么：**Dashboard → Incident API → Agent Runtime、工具、六服务，以及 Tool Error → Pinned Context → Repair → Resume。

**应该说什么：**“业务系统真实访问数据库、缓存和消息队列。Agent 只能调用允许的工具；Runtime 保存证据、错误和预算，并控制继续调查与恢复。”

## 01:00–02:30 · Replay

**点击哪里：**左侧 Investigation replay → Restart → 速度选 4× → Play。出现事件后 Pause，点一条 Original event，查看后 Close ×。再次 Play 让真实末尾报告出现；点击 Restart → Skip to Root Cause。

**页面出现什么：**按真实事件时间推进的 TOOL、EVIDENCE、ERROR、RECOVERY、ROOT CAUSE，以及末尾测试/报告。暂停后 Pause 按钮应禁用；根因跳转停在约 00:39。

**应该说什么：**“回放只加速时间，不改事件。模型找错函数、字段过长的错误也保留了。Runtime 返回反馈后继续调查。精确故障触发时间没有保存，页面只显示首次观察时间；这个 Incident 是评估操作员创建的，不能冒充自动检测。”

## 02:30–03:15 · Root Cause 与 Evidence

**点击哪里：**左侧 Root cause → Supporting evidence 中第一个 ID → Close ×；左侧 Evidence → LOGS → 展开第一条 Expand raw evidence → CODE。

**页面出现什么：**pricing 对 None discount 的减法报 TypeError、原始日志与源码证据、PARTIALLY_VERIFIED 及未排除的解释。

**应该说什么：**“模型把结论指向 order-service 的 pricing 路径。证据是工具实际读到的内容；部分验证不是概率，更不是百分之百正确。可以展开原始记录检查它是否支持结论。”

## 03:15–04:00 · Patch

**点击哪里：**左侧 AI patch → Baseline test failures → Original replay and dependency proof；可点击 Download candidate diff 保存真实 diff。

**页面出现什么：**两行新增代码；基线两项失败、候选九项通过；八个输入的 HTTP 500 从 100% 降为 0%；HIGH RISK / NOT DEPLOYED，Apply 禁用。

**应该说什么：**“这是模型生成的候选，在三服务和真实依赖里验证过。成功请求执行更多工作，P95 反而更高，不能宣传为延迟优化。财务逻辑仍需审查，没有上线。”

## 04:00–04:40 · Evaluation

**点击哪里：**左侧 Evaluation → 在最下方场景矩阵中找到 retry_storm 行，点击最右侧 V4.1 的 Incorrect → Close ×。

**页面出现什么：**各版本完成率、带分母的根因准确率、成本/延迟；原始错误判断。

**应该说什么：**“Rule 根因也有 7/8；最终 V4.1 完成八次、答对七次，重试风暴仍错。约 146 万 tokens 是八场累计用量，不是一次请求。八场样本不足以估计生产准确率。”

## 04:40–05:00 · Failure Story 收束

**点击哪里：**向上滚动到 Agent evolution，指出 V3 和 V3.1 的 FAILED EXPERIMENT；无需打开新窗口。

**页面出现什么：**V3 完成 2/8、V3.1 完成 1/8，失败没有隐藏。

**应该说什么：**“压缩上下文曾让工作流崩溃。最有价值的工程工作，是定位状态、反馈和恢复问题，而不是把结果刷成满分。当前 Critic 引用交接、成本和生产部署能力仍有限制。”

时间紧张时用 Overview → Skip to Root Cause → AI patch → Evaluation；不要省略 RECORDED、7/8 小样本和 NOT DEPLOYED 三个说明。
