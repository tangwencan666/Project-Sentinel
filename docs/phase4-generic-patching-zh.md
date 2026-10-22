# 受限业务函数候选修复：中文导读

[文档导航](index.md) · [英文原始记录](phase4-generic-patching.md) · [当前安全边界](sandbox-security.md)

引擎从有证据引用的源码路径选择 profile，而非读取 scenario ID。支持 pricing 的 `total`、payment 的 `normalize_amount`、order 的 `choose_item` 和 inventory 的 `normalize_product`；传输、数据库写入、缓存策略与故障控制不属于候选代码。

## 提案与校验

最终格式让模型输出完整替换源码，控制器基于实际不可变基线生成 Unified Diff。每次只修改一个文件，最多两次提案；检查精确路径、签名、默认值、注解、AST 与可调用函数。import、属性、循环、私有名、嵌套函数和任意调用被拒绝，测试、密钥、真值与基础设施文件受保护。

修复资格区分 `CODE_PATCH`、`CONFIG_CHANGE`、`INFRA_REMEDIATION`、`NO_AUTOMATIC_REMEDIATION`。不支持或未引用文件拒绝执行，配置与基础设施建议保持人工处理。财务修改为 HIGH risk，所有通用候选禁用自动 Apply，不能借旧版定价覆盖入口部署。

## 真实候选环境

基线/候选各启动 order、inventory、payment 三个 HTTP 进程。可信包装层执行参数化 PostgreSQL、Redis GET/SET/TTL、Kafka 生产消费；每次重放使用独立 schema、namespace 和 topic。Worker 有 CPU、内存、文件与超时约束、以非 root 运行，不获得模型密钥，但共享内核与基础设施，因此不是恶意 Python VM。

合同覆盖空折扣崩溃、非法金额、空目录和非法目录记录；后三者是附加组件检查，不替换八种故障。拒绝非法输入可能增加 4xx/503，需分别测业务违例、HTTP 5xx、健康结账、数据库行和消息事件。

## 保留的组件结果

首次真实模型 diff 格式探测 2/4 通过：pricing/order 成功，payment/inventory 出现 diff、`Try` 或单文件限制失败。失败提案从持久化状态单独保存。

后续源码格式探测在 165 项测试通过后完成 4/4，实际使用 10,393 Token；inventory 第一次使用不支持的 `Try`，第二次才通过。成功包含不可变合同和真实依赖 HTTP 重放。这些是组件验证，不是新增端到端 RCA 成功，所有候选未应用到业务源码。

旧评分器 `patch_generation_attempts` 不统计通用候选调用，不能据其为零推断未生成候选。应看 PatchGenerator 调用、Runtime 次数和工件。业务函数抽取发生在 V4 首轮之后，V1 原源码及 V2 的 14 文件 manifest 分别封存，不声称旧业务镜像逐字节复现。
