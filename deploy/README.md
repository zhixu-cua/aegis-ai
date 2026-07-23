# 部署与启动说明

## 1. 环境定位

- 本地开发环境：Windows 10/11
- 本地容器环境：Docker Desktop
- 目标部署环境：Linux 服务器
- 运行方式：统一使用容器运行，尽量减少宿主机差异带来的问题

## 2. 目录说明

- `docker-compose.yml`：基础依赖服务编排
- `deploy/schema.sql`：数据库初始化脚本
- `deploy/api-examples.json`：接口请求响应示例
- `deploy/.env.example`：环境变量模板
- `deploy/init-dev.ps1`：Windows 初始化脚本
- `deploy/init-prod.sh`：Linux 初始化脚本

## 3. Windows 本地开发建议

- IDE 可直接使用 IntelliJ IDEA、VS Code、PyCharm 等
- 本地先安装 Docker Desktop，并确认 `docker compose` 命令可用
- 先从 `deploy/.env.example` 复制出 `.env` 再启动
- 建议不要把业务逻辑写死为 `C:\xxx` 这样的本机路径
- 文档原文、附件等内容统一存入 MinIO，通过 `bucket + objectKey` 访问

### 3.1 启动基础依赖

在项目根目录执行：

```powershell
Copy-Item .\deploy\.env.example .\.env -Force
docker compose up -d
```

### 3.2 初始化数据库

```powershell
$pg = docker compose ps -q postgres
Get-Content .\deploy\schema.sql | docker exec -i $pg psql -U assistant -d assistant
```

你也可以直接执行一键脚本：

```powershell
.\deploy\init-dev.ps1
```

### 3.3 拉取本地模型

```powershell
docker compose exec -T ollama ollama pull qwen2.5:7b
```

说明：

- 模型名称可按你的机器配置替换
- 如果本机资源有限，可先使用更小模型验证链路

## 4. Linux 部署建议

- 服务器建议安装 Docker Engine 与 Compose 插件
- 建议使用独立目录，例如 `/opt/assistant`
- 建议通过 `systemd`、反向代理和日志采集进一步完善运维
- 先从 `deploy/.env.example` 复制出 `.env` 再启动

### 4.1 启动基础依赖

```bash
cp -n deploy/.env.example ./.env
docker compose up -d
```

### 4.2 初始化数据库

```bash
pg="$(docker compose ps -q postgres)"
docker exec -i "$pg" psql -U assistant -d assistant < deploy/schema.sql
```

### 4.3 拉取模型

```bash
docker compose exec -T ollama ollama pull qwen2.5:7b
```

你也可以直接执行一键脚本：

```bash
bash deploy/init-prod.sh
```

## 5. 跨环境约束

- 所有服务连接信息使用环境变量管理
- 不在代码、SQL 或接口设计中传递宿主机绝对路径
- 文件定位统一使用对象存储键，而不是本地磁盘路径
- 容器内默认按 Linux 环境设计，因此即使在 Windows 开发，也尽量通过容器验证

## 6. 后续建议

- 增加 `.env` 管理数据库、Redis、MinIO、Ollama 连接参数
- 为 Spring Boot 与 FastAPI 构建服务镜像（见 `backend/Dockerfile` 与 `ai-service/Dockerfile`）
- Linux 上接入 Nginx 做统一入口和 HTTPS
