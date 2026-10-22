# 只读演示与本地 Live Lab 部署

Project Sentinel 面向微服务故障调查与受限候选补丁验证。默认部署仅包含前端、只读 FastAPI 服务和脱敏历史记录，不包含 PostgreSQL、Redis、Kafka、Jaeger、故障实验室或 Live Provider Runtime，也不需要 API Key。

## 启动本地只读演示

需要 Docker Engine/Desktop 与 Docker Compose v2。在仓库根目录执行：

```sh
docker compose up -d --build
```

打开 [本地演示](http://localhost:18082)。首次构建需要下载 Python 依赖，默认端口仅绑定回环地址。录制模式的 `.env` 是可选文件；复制 `.env.example` 仅用于调整端口和 Host 等设置，不需要填写密钥。已有 `.env` 时直接编辑，避免覆盖原配置。

```sh
docker compose ps
docker compose logs --tail=50 sentinel-demo
```

端口冲突时，可在 PowerShell 中执行 `$env:DEMO_PORT = "18084"`，再运行启动命令并访问对应端口。可选环境检查需要本机 Python：

```sh
python scripts/check_environment.py --mode recorded
```

自定义端口时附加 `--port 18084`。该脚本检查 Docker、Compose 和只读 API，不发送模型请求。停止演示使用 `docker compose down`。

## 预留的服务器部署方式

仓库提供部署路径，尚未因此购买或部署域名、服务器或付费服务。以下域名是示例，不是可访问的项目地址。

若未来使用 `sentinel.example.com`，设置 `DEMO_ALLOWED_HOSTS=sentinel.example.com,localhost,127.0.0.1,sentinel-demo`，保留 `PUBLIC_DEMO_MODE=true`，构建同一个只读镜像。在回环端口 `18082` 前配置 TLS 反向代理，转发正确的 Host，并设置请求大小、速率和超时限制。nginx 路径配置示例：

```nginx
location / {
    proxy_pass http://127.0.0.1:18082;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 16k;
}
```

TLS 证书由部署主机的证书工具管理，同时监控服务端错误、维护系统和容器更新、备份发布产物。部署时应重新检查依赖漏洞；现有有限测试不等于任意服务器入侵或拒绝服务攻击防护认证。

## 只读边界与验证范围

- 公开镜像仅复制 `sentinel/public_demo.py` 与空包初始化文件，不复制数据库、Provider、工具或 Live Runtime 模块，也不挂载密钥。
- 路由前拒绝所有非 GET/HEAD 请求并返回 403；不存在工具、配置和上传执行接口，`/live.html` 被拒绝。
- 默认容器以非 root 用户运行，文件系统只读、移除 capabilities 并限制资源；不挂载数据库凭据或 Docker socket。
- 响应设置 CSP 和 Host allowlist，不启用宽松 CORS。原始观测以转义文本展示，文档访问使用文件名白名单。
- 启动时校验数据 manifest；这可以发现意外修改，但不能阻止管理员同时改写数据与清单。

实现依据：[Dockerfile.demo](../Dockerfile.demo)、[compose.yaml](../compose.yaml)、[public_demo.py](../sentinel/public_demo.py)。已知依赖与隔离限制见 [独立审计](independent-final-audit.md)。

## 显式启用本地 Live Lab

`compose.live.yaml` 仅用于可信本机环境。尚无 `.env` 时复制模板：

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

在本地配置 `LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY`，并显式设置 `LIVE_AI_ENABLED=true`。密钥不写入文档或 Git 提交。

```sh
docker compose -f compose.live.yaml up -d --build
```

打开 [Live 工作区](http://localhost:18083/live.html)。Live 调查会消耗真实模型额度，并允许操作本地故障实验。默认 `LIVE_AI_ENABLED=false` 会禁用变更控制、检测派发和自动检查点恢复，遥测仍可读取。完整实验室没有生产级多租户鉴权，不应暴露到公网。

需要检查环境时执行 `python scripts/check_environment.py --mode live`，该检查不触发付费连通性请求。本次文档更新未启动 Live Lab，也未重跑付费 Benchmark。

Recorded Demo 与 Live Lab 使用不同的 Compose 项目名和端口。停止时使用对应配置：

```sh
docker compose down
docker compose -f compose.live.yaml down
```

按实际运行模式选择其中一条即可，切换模式不需要删除数据卷。既有实验数据卷和冻结镜像可继续保留。更多运行步骤见 [中文首页](../README.md#本地部署)，原英文首页保留于 [README_EN.md](../README_EN.md)。
