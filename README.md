# Aegis AI 智能网站群售后助手

Aegis AI 智能售后助手是一个基于检索增强生成（RAG）技术与大语言模型（LLM）构建的企业级智能问答系统。它旨在为用户提供准确、高效的网站群使用及售后支持服务。系统采用前后端分离的现代化架构，通过微服务设计实现了高内聚低耦合，支持多用户管理、多会话记录、知识库动态上传解析以及实时的流式打字机交互体验。

---

## 🚀 核心特性

- **高精度 RAG 混合检索**：融合了基于 `pgvector` 的语义向量检索与自研轻量级 `BM25` 关键词检索，并通过 RRF (Reciprocal Rank Fusion) 算法进行结果倒排融合，极大提升了对售后专业术语的检索准确率。
- **动态 Prompt 引擎**：根据知识库检索结果动态切换大模型 Prompt 策略。若命中相关文档则采用严格事实参考模式；若无相关文档则优雅切换至通用闲聊/兜底模式，有效控制小参数模型的“幻觉”现象。
- **SSE 流式实时响应**：打通了 `Python (FastAPI) -> Java (Spring Boot) -> Vue3` 的全链路 SSE（Server-Sent Events）打字机流式传输架构。即使是在生成长文本时，用户也能获得极低的首字等待时间（TTFT）与丝滑的实时输出体验。
- **沉浸式现代化 UI**：采用 Vue3 + Flex 响应式布局，完美适配全屏展示。集成“登录/注册”一体化卡片、多会话历史侧边栏以及优雅的 Markdown 语法与代码高亮渲染。
- **全链路操作审计**：对用户的提问、模型调用耗时（CostMs）、文档上传及异常报错等核心行为进行结构化日志入库，方便后期追踪调优。

---

## 🛠️ 技术栈详情

### 1. 前端 (Frontend)
- **核心框架**：Vue 3 (Composition API, `<script setup>`) + Vite 构建工具。
- **路由管理**：Vue Router 4。
- **网络通信**：
  - Axios (拦截器统一处理 401 及业务错误)。
  - 原生 `fetch` API + `ReadableStream` (用于解析 SSE 复杂流式数据)。
- **样式与渲染**：
  - 原生 CSS (响应式 Flex 布局，无依赖)。
  - `marked` (将大模型返回的 Markdown 文本解析为 HTML)。
  - `highlight.js` (集成 GitHub 浅色主题代码高亮)。
- **认证管理**：基于 `localStorage` 的轻量级 Token 存储。

### 2. 核心业务后端 (Backend - Java)
- **核心框架**：Spring Boot 3。
- **数据持久化**：
  - Spring Data JPA (Hibernate 6)。
  - `hypersistence-utils-hibernate-63` (用于将 PostgreSQL 的 `jsonb` 字段无缝映射为 Java 对象)。
- **认证与鉴权**：
  - Sa-Token (轻量级权限认证框架，提供简洁的拦截器与 `StpUtil` 工具)。
- **跨服务通信**：Spring `RestTemplate` + `SseEmitter` 异步线程转发。
- **数据库**：PostgreSQL (关系型数据存储，含 JSONB 特性)。

### 3. AI 微服务后端 (AI Service - Python)
- **核心框架**：FastAPI (高性能异步 Web 框架) + Uvicorn。
- **模型与推理**：
  - Ollama (本地大模型部署引擎，托管 `qwen3:0.6b` / `qwen:1.8b` 等开源 LLM)。
  - `nomic-embed-text` (用于生成文本的高维稠密向量)。
- **混合检索核心**：
  - `asyncpg` (异步并发连接 PostgreSQL，实现高吞吐的 SQL 操作)。
  - `pgvector` (PostgreSQL 向量插件，执行高效率的余弦相似度计算)。
  - `jieba` (中文分词工具，用于自研 BM25 词频计算)。
- **响应机制**：FastAPI `StreamingResponse` + Python Generator (Yield 生成器)，实现事件流数据的实时抛出。

---

## 🏗️ 架构数据流 (Data Flow)

1. **用户提问**：用户在 Vue 前端输入问题，前端通过 `fetch` 携带 Token 发起 `/api/assistant/chat/stream` POST 请求。
2. **鉴权与会话记录**：Spring Boot 拦截器通过 Sa-Token 校验鉴权。`ChatService` 生成并保存用户消息至 PostgreSQL 的 `assistant_message` 表。
3. **透传至 AI 服务**：Spring Boot 开启新线程，使用 `RestTemplate` 异步调用 FastAPI 的 `/internal/rag/query` 接口。
4. **知识库混合检索**：
   - FastAPI 调用 Ollama 将用户问题转换为 Embedding 向量。
   - 使用 `asyncpg` 查询 PostgreSQL 的 `kb_chunk` 表，获取 Vector Top K 候选片段。
   - 同步执行 BM25 关键词词频匹配，得出 BM25 Top K。
   - 执行 RRF 算法融合两种得分，最终得出最佳匹配文档（Context）。
5. **LLM 思考与流式吐出**：FastAPI 组装动态 Prompt，请求 Ollama 进行流式推理，通过 `yield` 将生成结果逐块（Chunk）返回给 Spring Boot。
6. **双层流式转发**：Spring Boot 接收到 Python 的流式块后，使用 Jackson 序列化，包裹成符合 SSE 协议的 `data:` 格式，通过 `SseEmitter` 实时推送至 Vue 前端。
7. **前端响应式渲染**：Vue 接收 SSE 数据包，利用正则表达式和 JSON 容错解析机制，累加字符串并通过 Proxy 响应式对象触发视图实时渲染，呈现完美的打字机效果。

---

## 📦 部署与运行指南

### 依赖环境
- JDK 17+
- Node.js 18+ (配合 npm / pnpm)
- Python 3.10+
- PostgreSQL 15+ (必须安装并启用 `pgvector` 扩展)
- Ollama

### 启动步骤
1. **启动数据库与 AI 底层**
   - 确保 PostgreSQL 正在运行 (默认端口 5433)。
   - 启动 Ollama，并确保模型已就绪：`ollama run qwen3:0.6b` 和 `ollama pull nomic-embed-text`。
2. **启动 AI 服务 (FastAPI)**
   - 进入 `ai-service` 目录，安装依赖：`pip install fastapi uvicorn asyncpg jieba`
   - 启动服务：`uvicorn api.main:app --host 127.0.0.1 --port 8000`
3. **启动 Java 业务服务**
   - 进入 `backend` 目录，使用 Maven 编译并启动 Spring Boot 应用 (默认端口 8082)。
4. **启动前端服务**
   - 进入 `assistant-web` 目录。
   - 安装依赖：`npm install`
   - 启动 Vite 开发服务器：`npm run dev`

### 注意事项
- 由于系统涉及多线程与长时间的 LLM 推理，Spring Boot 与 Axios/Fetch 的超时时间均已统一上调至 300000ms（5分钟）。
- 若部署在非本地环境，需在 `ai-service` 中调整跨域策略及相关 IP 配置。
