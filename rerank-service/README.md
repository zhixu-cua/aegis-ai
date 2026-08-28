# 远程重排微服务（Rerank Service）

Ollama 官方**没有** `/api/rerank` 接口，所以重排序需要独立部署。
本服务在**远程 GPU 服务器**上用 sentence-transformers 加载交叉编码器
（`BAAI/bge-reranker-v2-m3`，中文效果最佳；失败自动回退 `bge-reranker-large`），
通过 HTTP 暴露给本地 ai-service 调用。

> 本地（无 GPU 的 Windows 机器）**不需要**安装任何深度学习依赖，
> 只通过 HTTP 请求本服务。

## 1. 部署（在远程 GPU 服务器上）

```bash
# 进入 rerank-service 目录
cd rerank-service

# 安装依赖（torch 较大，建议用 GPU 版安装方式，如 pip install torch --index-url https://download.pytorch.org/whl/cu121）
pip install -r requirements.txt

# 启动（首次启动会自动从 HuggingFace 下载 bge-reranker-v2-m3，约 1.3GB，之后加载到显存）
uvicorn main:app --host 0.0.0.0 --port 8001
```

> 如果 HuggingFace 无法直连（国内网络），可设置镜像：
> `export HF_ENDPOINT=https://hf-mirror.com`

## 2. 本地 ai-service 配置

在 ai-service 的环境变量里设置：

```
RERANK_MODE=remote
RERANK_API_URL=http://<远程服务器IP>:8001
```

- 若你的 GPU 服务器就是跑 Ollama 的那台，IP 和 `OLLAMA_BASE_URL` 相同。
- `RERANK_MIN_SCORE=0.0`（默认）：bge-reranker 输出 logits，>0 即相关；想更严格可设 `0.5`。

## 3. 验证

```bash
# 在远程服务器本机
curl http://127.0.0.1:8001/health
# 期望: {"status":"UP","model":"BAAI/bge-reranker-v2-m3","device":"cuda"}

# 测试重排
curl -X POST http://127.0.0.1:8001/rerank \
  -H "Content-Type: application/json" \
  -d '{"query":"数据库连不上怎么办","documents":["重启数据库服务即可","今天天气不错"]}'
```

## 4. 可选配置

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | 首选模型 |
| `RERANK_MAX_LEN` | `512` | 输入最大长度 |
| `PORT` | `8001` | 监听端口 |

## 5. 接口说明

- `GET /health` — 健康检查
- `POST /rerank` — 请求 `{"query":"...","documents":["...","..."]}`，
  响应 `{"model":"...","results":[{"index":0,"relevance_score":0.9},...]}`（按分数降序）
