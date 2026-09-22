# Future Work · 未实现，不属于本轮交付

以下是有意义的后续方向，不是当前能力，也不承诺收益。

| 方向 | 要解决什么 | 应如何验证 |
|---|---|---|
| Larger benchmark | 八场景不足以衡量泛化 | 独立作者设计未见故障、重复运行、预先定义评分，保留失败。 |
| Multiple models | 单模型结论有限 | 同一环境与工具权限下比较完成率、正确率、延迟和用量。 |
| Cross-model Critic | 同模型相关错误与证据遗漏 | 先保证引用交接完整，再测独立复核是否改善错误接受/拒绝。 |
| More services | 当前依赖复杂度有限 | 增加真实业务边界后重新验证 Trace 关联与错误传播。 |
| Real Kubernetes | 目前只是 Docker Compose | 真正部署、故障隔离与恢复实验，未做前不列为已掌握的项目实现。 |
| Production observability integration | 项目内工具尚未接企业环境 | 使用明确授权的只读身份、脱敏、采样与审计。 |
| Cost-aware planning | 重复上下文与工具读取成本高 | 联合衡量完整工作流成本、证据覆盖和漏诊，不能只比 token 降幅。 |
| Human approval workflow | 候选尚无完整生产发布治理 | 权限、审批、灰度、回滚、幂等及不可篡改发布审计。 |

本轮不实施以上功能，不启动新的付费 Benchmark，不覆盖任何冻结结果。
