# Aegis AI 智能售后助手 - 知识库自动化管理需求说明书

## 1. 引言

### 1.1 需求背景
当前 Aegis AI 售后助手已经实现了基于 RAG（检索增强生成）的智能问答能力。然而，现阶段知识库的文档更新高度依赖人工逐一手动上传。这不仅操作繁琐、时效性差，而且在多租户场景下缺乏严格的版本管理和权限隔离。为了提升用户体验和系统自动化程度，亟需引入“自动化知识库管理”功能。

### 1.2 建设目标
构建一套零感知、全自动的知识库管理体系。用户只需在系统中配置数据源（如本地文件夹、腾讯云 COS 等），后续便可像管理本地普通文件夹一样维护文档。系统将在后台自动完成文件的同步、解析、文本切片、向量化存储以及索引更新，并在前端提供实时的状态反馈。

---

## 2. 整体架构与技术选型分析

结合现有系统（Vue 3 + Spring Boot 3 + FastAPI + Redis + PostgreSQL/pgvector）的基础，本期需求将在现有架构上进行无缝扩展：

- **文件监听**：引入 Python 的 `watchdog` 实现本地文件夹的变更监控。
- **消息队列**：复用现有的 Redis 组件，使用 `Redis Stream` 实现事件的生产与消费解耦。
- **实时推送**：在 Spring Boot 业务层增加 `WebSocket` 服务，用于向 Vue 前端实时推送文档处理状态。
- **对象存储**：引入腾讯云 COS SDK，支持云端数据源的自动拉取与同步。

---

## 3. 功能需求详细说明

### 3.1 知识库数据源配置管理

**需求描述**：
用户需要在前端界面配置需要监听的数据源。支持的数据源类型包括“本地文件夹”和“云端存储（如 COS）”。系统需记录数据源路径、同步频率、租户归属等信息，并支持对数据源的增删改查。

**详细功能**：
1. **知识库管理主页**：展示当前所有已配置的数据源列表及其整体同步状态。
2. **数据源配置弹窗**：支持填写数据源名称、选择类型（local/cos）、输入路径/鉴权配置。
3. **后端管理 API**：Spring Boot 提供数据源的 CRUD 接口，并负责在配置变更时通知监听模块。

**关联代码文件**：
- `document/code/deepseek_vue_20260807_524ed7.vue` (知识库管理页面 `KnowledgeManage.vue`)
- `document/code/deepseek_vue_20260807_93dbf6.vue` (数据源配置组件 `DataSourceConfig.vue`)
- `document/code/deepseek_vue_20260807_b59c8c.vue` (新建数据源对话框 `CreateDatasourceDialog.vue`)
- `document/code/deepseek_vue_20260807_ed9b05.vue` (侧边栏更新 `Sidebar.vue`)
- `document/code/deepseek_typescript_20260807_211ab4.ts` (前端路由配置更新 `router/index.ts`)
- `document/code/deepseek_java_20260807_eba488.java` (Java 控制器 `KbDatasourceController.java`)
- `document/code/deepseek_java_20260807_725c43.java` (Java 服务实现 `KbDatasourceServiceImpl.java`)

### 3.2 文件变动监听与事件分发

**需求描述**：
系统需根据配置的数据源，实时或定时监控文件目录的变动（新增、修改、删除）。一旦发现变动，立即生成处理事件并推入消息队列，确保文档变动不丢失。

**详细功能**：
1. **本地监听器**：FastAPI 服务启动时挂载 watchdog，递归监听指定目录的变动事件（过滤临时文件与隐藏文件）。
2. **COS 同步器**：对于 COS 数据源，定时拉取文件列表并比对本地/库内哈希，发现差异则触发同步。
3. **事件投递**：将文件变动事件（`created`, `modified`, `deleted`）写入 Redis Stream。

**关联代码文件**：
- `document/code/deepseek_python_20260807_0a80d1.py` (文件监听器 `listener.py`)
- `document/code/deepseek_python_20260807_7307b0.py` (COS 连接器 `connector_cos.py`)
- `document/code/deepseek_python_20260807_49325b.py` (FastAPI 启动挂载 `main.py`)
- `document/code/deepseek_java_20260807_b7e9ba.java` (Java Redis Stream 工具类 `RedisStreamUtil.java`)

### 3.3 文档自动化处理流水线 (Worker)

**需求描述**：
后台消费者（Worker）独立从 Redis Stream 获取待处理文档事件，执行完整的 RAG 预处理流程，并将最终的向量数据安全落库。

**详细功能**：
1. **任务消费**：异步从 Redis Stream 消费事件，支持故障重试。
2. **多格式解析**：支持对 PDF、Word (docx/doc)、TXT、Excel、Markdown 的纯文本解析，兼容系统现有的 RapidOCR 和 PyMuPDF 增强解析能力。
3. **智能切块**：将长文档切分为适合向量化的 Chunk。
4. **向量化与存储**：调用 Ollama 嵌入模型生成向量，写入 PostgreSQL 的 `pgvector` 扩展表。针对“修改”和“删除”事件，需对旧版 Chunk 执行软删除操作。

**关联代码文件**：
- `document/code/deepseek_python_20260807_7ea4a1.py` (文档处理任务消费者 `worker.py`)
- `document/code/deepseek_python_20260807_eabaf4.py` (文档解析器 `parser.py`)
- `document/code/deepseek_python_20260807_89f51d.py` (文档切块器 `chunker.py`)
- `document/code/deepseek_python_20260807_cf1469.py` (向量存储与数据库操作 `vector_store.py`)

### 3.4 实时状态推送与反馈

**需求描述**：
为了让客户拥有“所见即所得”的体验，系统需要将底层 AI 服务的文档处理进度实时推送到前端页面展示。

**详细功能**：
1. Python Worker 在文档处理的不同阶段（如解析中、切块中、已完成、失败），通过 HTTP 调用 Spring Boot 的内部接口上报状态。
2. Spring Boot 接收状态后，更新数据库记录，并通过 WebSocket 推送给当前在线的对应租户前端。
3. Vue 前端通过 WebSocket 监听事件，动态更新页面上的文件同步进度条和状态标签。

**关联代码文件**：
- `document/code/deepseek_java_20260807_45058e.java` (Java WebSocket 服务 `WebSocketServer.java`)
- `document/code/deepseek_typescript_20260807_5aa1e7.ts` (前端 WebSocket 组合式函数 `useWebSocket.ts`)

---

## 4. 数据库设计需求

为了支撑数据源配置和文档处理记录，需对现有的 PostgreSQL 数据库进行结构扩充：

1. **新建 `kb_datasource` 表**：
   用于存储数据源名称、类型（local/cos）、详细配置（JSONB格式）、同步频率及租户信息。
   - **关联代码**：`document/code/deepseek_sql_20260807_131f53.sql`, `document/code/deepseek_java_20260807_2da63a.java` (`KbDatasource.java`)

2. **新建 `kb_document` 表**：
   用于记录每次文件处理的元数据，包括文件路径、哈希值（去重用）、文件大小、当前处理状态（pending/processing/completed/failed）以及关联的数据源 ID。
   - **关联代码**：`document/code/deepseek_sql_20260807_fea43e.sql`, `document/code/deepseek_java_20260807_9361d4.java` (`KbDocument.java`)

3. **扩展现有 `kb_chunk` 表**：
   为现有的向量块表增加 `document_id`（关联文档记录）、`datasource_id`（冗余字段加速检索）、`is_deleted`（软删除标记）和 `version`（版本号）字段，以支持文档的版本迭代和安全删除。
   - **关联代码**：`document/code/deepseek_sql_20260807_023d0a.sql`

---

## 5. 非功能性与实施需求

1. **零破坏性**：改造必须在现有架构上以增量形式进行，严禁破坏已有的手动上传和问答检索流程。
2. **健壮性**：文档解析阶段必须做好单文件异常隔离（try-except），防止个别损坏文档导致整个 Worker 进程崩溃。
3. **跨平台兼容**：文件路径处理和监听机制需同时兼容 Windows 开发环境和 Linux 生产环境。
4. **性能约束**：考虑到本地环境部署（未采用 Docker），大并发文件同步时应通过 Redis Stream 的 MaxLen 或消费速率控制来限制系统资源占用，防止内存溢出。
