# 项目状态与演示入口：中文说明

[文档导航](index.md) · [保留的英文交付状态](../FINAL_STATUS.md)

Project Sentinel 是六服务本地故障调查与受限候选验证项目。当前默认入口是历史录制展示，不是持续运行的生产电商或自动修复平台。

## 录制了什么

默认展示 V4.1 run `759044e6-c016-489b-a459-137ca4846462`，2026-09-22 UTC 录制、模型 deepseek-chat。204 个原始有序事件、19 份证据、定价候选和测试属于同一 run。播放不执行工具；精确注入时间未知，展示首次观察与操作员请求创建事故的时间。

## 如何启动

```sh
docker compose up -d --build
```

访问 [本地录制演示](http://localhost:18082)。需要 Docker 与首次下载，无需 `.env` 或密钥。镜像准备后才支持无外部依赖运行，源码 ZIP 不含镜像。

完整 Live Lab 使用 `compose.live.yaml`、端口 `18083`；只有显式配置模型与 `LIVE_AI_ENABLED=true` 才允许真实调查。故障注入、Apply、实时模型、shell、数据库写入、配置上传均不在公开模式中提供。

## 历史结果与当前状态

冻结 V4.1 完成 8/8、根因与服务 7/8，1,461,870 工作流 Token、平均 78.75 秒；八场均部分验证、重试风暴仍错。189 为冻结门禁，267 为旧 Phase 5、287 为独立审计后端批次，前端历史 17。不能混为当前源码或生产准确率。

当前引用保护未重跑完整付费 Benchmark；沙箱共享内核、补丁只覆盖四类函数、Live 缺完整生产鉴权/租约/审批，候选 NOT DEPLOYED。详细见 [限制](limitations.md)、[部署](deployment-public-demo.md) 与 [本次验证](localization-validation.md)。

演示路径：[30 秒介绍](pitch-30s.md) → [五分钟演示](demo-5min.md) → [十分钟技术演示](demo-10min.md) → [面试问答](interview-qa.md)。英文交付包路径仅是历史本地产物，不代表 Git 仓库包含 ZIP 或已部署公网。
