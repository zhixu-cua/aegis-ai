# Aegis AI 检索管线企业级改造与多模态智能体演进方案

> 版本：v1.0
> 目标：把当前「演示级 RAG」升级为「企业级 RAG」，并为后续「多模态智能体」预留演进空间。
> 原则：尽量沿用现有技术栈（PostgreSQL+pgvector / Redis / FastAPI / Spring Boot / Ollama），以「可落地、可灰度、可回滚、可评测」为第一优先级。

---

## 1. 现状评估（结论先行）

**总体评级：DEMO 级（演示可用，不可直接上生产）。**

能跑通「上传 → 切片 → 向量化 → 混合检索 → 生成」主链路，但离企业级在**性能、质量、可观测、可评测、安全、可运维**六个维度都存在系统性缺口。以下逐模块给出结论与证据。

| 模块 | 当前评级 | 一句话结论 |
|------|---------|-----------|
| 混合检索 | ⭐⭐ | 有 pgvector + 自研 BM25 + RRF 的形，但 BM25 是"无索引全量扫描"，规模稍大即不可用 |
| 重排序 | ⭐ | 实际未启用（依赖未装），且无分数校准/阈值/回退 |
| 切片 | ⭐⭐ | 递归字符切分，无语义/结构感知，chunk 无元数据、无父子块 |
| 数据清洗 | ⭐⭐ | 正则级清洗 + 关键词级注入防护，会误伤知识内容 |
| 入库 | ⭐⭐ | 逐条向量化 + sleep，无批处理/重试/死信/指标 |
| 评测 | ⭐ | 完全没有评测体系 |
| 可观测 | ⭐ | 以 `print` 为主，无结构化日志/Trace/指标 |
| 安全 | ⭐ | 无输出护栏、无越权细化、注入防护可被轻易绕过 |

---

## 2. 现状问题清单（可定位到代码）

### 2.1 混合检索

1. **BM25 是无索引的全量扫描**（`ai-service/api/routes/chat.py` 的 `SimpleBM25`）：
   - 每次请求先 `SELECT ... chunk_text ...` 把**整个过滤语料**拉进内存，再用 Python 逐词算 BM25。
   - 复杂度 O(语料块数 × 词数)，无倒排索引、无 doc_length/IDF 缓存、无持久化。
   - 语料超过 1~2 万块后，单次请求延迟线性恶化，内存压力大，不可上生产。

2. **向量检索无元数据过滤**：只有 `datasourceId/tenantId` 两个粗粒度过滤，缺「文档类型、时间范围、站点、标签、状态」等业务过滤维度。

3. **无查询理解**：缺 query rewriting / 意图分类 / 多查询（multi-query）/ HyDE，长尾问法、口语化问法召回差。

4. **向量索引无版本管理**：embedding 模型切换（nomic-embed-text 768 维 → bge-m3 1024 维）没有 schema 迁移策略，靠手工重建，容易造成维度不匹配的静默错误。

5. **每次请求新建 DB 连接**：`chat.py` 用 `asyncpg.connect()` 临时建连，未复用 `main.py` 里已有的 `pg_pool`，连接开销大且不可控。

### 2.2 重排序

1. **实际未启用**：`sentence-transformers` 未安装（实测 `NOT INSTALLED`），`reranker` 恒为 `None`，退化成 RRF TopK。
2. **无分数校准**：cross-encoder 输出 logits 直接排序，无 sigmoid 归一化、无自适应阈值、无「低于阈值则拒答」的稳定策略。
3. **无回退与降级**：无「重排器不可用/超时 → 确定性降级」的完整链路。
4. **单阶段**：无「召回 → 精排 → 重排」的三级漏斗，候选集与最终集合边界不清晰。

### 2.3 切片

1. **无语义/结构感知**（`api/services/ingestion/chunker.py`）：`_recursive_split` 只按「换行/句号/逗号」等字符分隔符切，不理解 Markdown 标题层级、列表、表格、代码块边界。
2. **chunk 无元数据**：`kb_chunk` 只有 `chunk_index/chunk_text/embedding`，缺少 `section_title/document_title/path/heading_path`，导致检索命中的片段「丢失来龙去脉」。
3. **无父子分块（small-to-big）**：检索用小块、回答用大块的标准做法缺失，长答案上下文不足（正是之前「只覆盖一半内容」的深层原因）。
4. **存在确定性 bug**：`chunk_text` 的 `start_char = text.find(chunk_text)` 找到的是「第一次出现位置」，重复段落时定位错误。

### 2.4 数据清洗

1. **PII 脱敏会破坏知识**：手机号/身份证/邮箱正则替换后，文档里的「示例手机号/示例配置」会被打码，反而损失了知识（售后文档里常含示例值）。
2. **提示注入防护形同虚设**（`cleaner.py` 的 `injection_patterns`）：仅关键词正则，真实注入（角色扮演、间接指令、编码混淆）可轻易绕过。
3. **清洗规则不可配置、不可观测**：清洗规则写死在代码里，无法按租户/文档类型差异化，也没有「清洗前后 diff」审计。

### 2.5 入库

1. **逐条向量化 + sleep**（`vector_store.py`）：`for chunk: await embeddings(); await asyncio.sleep(0.05)`，无批处理，大文档入库极慢。
2. **无重试 / 无死信队列**：worker 消费 Redis Stream，处理失败仅打印，消息可能丢失或重复。
3. **幂等性依赖 file_hash 但非强一致**：并发 upsert 同一文件可能产生重复 chunk。
4. **无任务级指标**：吞吐、成功率、P99 延迟、失败原因分布均无。

### 2.6 评测 / 可观测 / 安全

1. **无评测**：没有评测集、没有召回率/准确率/忠实度（faithfulness）自动化评估，改完参数无法量化「变好还是变坏」。
2. **无可观测**：以 `print` 为主，无结构化日志、无 TraceID 贯穿、无指标（Prometheus）。
3. **安全缺口**：无输出护栏（guardrails）、无内容审核、无细粒度数据权限（tenant 级别可以绕过）、内部接口 `/internal/**` 依赖内网隔离但无鉴权兜底。

---

## 3. 企业级目标架构

### 3.1 检索漏斗（核心改造点）

```
用户问题
  │
  ▼
① 查询理解（Query Understanding）
   - 意图分类 / 改写（口语→书面）/ 多查询 / HyDE（可选）
  │
  ▼
② 多路召回（Recall，宽召回，低延迟）
   - 向量召回（pgvector HNSW + 元数据过滤）
   - 关键词召回（BM25 索引：PostgreSQL tsvector+zhparser 或 ES）
   - 精确/结构化召回（文档标题、标签、表格键值）
  │
  ▼
③ 精排融合（Fusion）
   - RRF（可配置权重）+ 分数归一化 + 去重
  │
  ▼
④ 重排序（Rerank，精排，高精度）
   - cross-encoder（bge-reranker）+ sigmoid 校准 + 自适应阈值 + 拒答判定
  │
  ▼
⑤ 上下文装配（Context Assembly）
   - 父子块展开（child 命中 → 回填 parent 大块 + 标题路径）
   - 元数据注入（文档名/章节/来源）+ Token 预算截断
  │
  ▼
⑥ 生成（Generation）+ 护栏（Guardrails）
```

### 3.2 目标数据模型（增量变更）

在现有表基础上新增（不动老字段，保证可灰度）：

```sql
-- 1) chunk 增加结构元数据与父子关系
ALTER TABLE kb_chunk
  ADD COLUMN IF NOT EXISTS parent_id bigint,             -- 父块 id（small-to-big）
  ADD COLUMN IF NOT EXISTS section_title text,           -- 所在章节标题
  ADD COLUMN IF NOT EXISTS heading_path text,            -- 标题路径，如 "安装 > 配置 > 数据库"
  ADD COLUMN IF NOT EXISTS content_type text DEFAULT 'text', -- text/table/code/image
  ADD COLUMN IF NOT EXISTS chunk_meta jsonb;             -- 业务元数据（标签、时间、站点等）

-- 2) BM25 索引（PostgreSQL 全文检索方案）
ALTER TABLE kb_chunk ADD COLUMN IF NOT EXISTS ts tsvector;
CREATE INDEX IF NOT EXISTS idx_kb_chunk_ts ON kb_chunk USING GIN(ts);

-- 3) 入库任务与死信
CREATE TABLE IF NOT EXISTS ingest_task (
  id bigserial PRIMARY KEY,
  datasource_id bigint,
  document_id bigint,
  file_path text,
  file_hash text,
  status text,              -- pending/processing/completed/failed/dead
  attempt int DEFAULT 0,
  max_attempt int DEFAULT 3,
  error_msg text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- 4) 评测集与评测结果
CREATE TABLE IF NOT EXISTS eval_case (
  id bigserial PRIMARY KEY,
  question text,
  ground_truth text,        -- 标准答案/相关文档 id
  ref_chunk_ids bigint[],
  tags text[]
);
CREATE TABLE IF NOT EXISTS eval_result (
  id bigserial PRIMARY KEY,
  run_id text,
  case_id bigint,
  metrics jsonb,            -- 召回/准确率/忠实度等
  created_at timestamptz DEFAULT now()
);
```

> 说明：向量维度从 768 → 1024（bge-m3）的迁移要单独出迁移脚本 + 双写灰度，见 §7。

---

## 4. 分阶段改造路线图

### 4.1 P0 —— 企业级基础（1~2 周，先止血）

**目标：把「会漏、会慢、不可观测」的基础问题先解决。**

| # | 任务 | 技术要点 | 验收标准 |
|---|------|---------|---------|
| 1 | **复用连接池** | `chat.py` 复用 `pg_pool`，去掉临时 `asyncpg.connect` | 高并发下连接数稳定 |
| 2 | **BM25 索引化** | 用 PG `tsvector` + `zhparser`（中文分词）建 GIN 索引，替代 Python 全量扫描 | 1 万块语料下单次检索 < 100ms |
| 3 | **入库批处理** | `vector_store.py` 改批量 embedding（Ollama `/api/embed` 批量接口），去掉 `sleep(0.05)` | 大文档入库耗时下降 5~10 倍 |
| 4 | **入库重试 + 死信** | 引入 `ingest_task` 状态机，失败重试 3 次后进死信，可人工重放 | 失败不丢、可追踪 |
| 5 | **重排序真正启用 + 校准** | 安装 `sentence-transformers` + `bge-reranker-large`，加 sigmoid 归一化 + 阈值 + 无重排器时确定性回退 | 重排开启后命中率可量化提升 |
| 6 | **结构化日志** | 全链路 `logging` + `request_id` 贯穿 Java/Python | 一次请求可串起完整链路日志 |
| 7 | **切片元数据 + 父子块** | chunk 增加 `section_title/heading_path/parent_id`，检索命中后回填父块 | 长答案上下文完整（根治「只覆盖一半」） |

### 4.2 P1 —— 企业级增强（2~4 周）

**目标：把「准确率、体验、可运维」拉到生产水位。**

| # | 任务 | 技术要点 |
|---|------|---------|
| 1 | **查询理解** | 意图分类 + query rewriting + 多查询 + HyDE（可选），召回率提升 |
| 2 | **评测体系** | 构建评测集（问题 + 标准答案 + 相关文档），接入 RAGAS（faithfulness/answer relevance/context relevance）+ 召回评测，CI 门禁 |
| 3 | **缓存** | embedding 缓存、热点问答缓存、语义缓存（Semantic Cache） |
| 4 | **可观测性** | OpenTelemetry（Trace）+ Prometheus 指标 + 告警（召回命中率、拒答率、P99、入库成功率） |
| 5 | **反馈闭环** | 用户点赞/点踩 → 回流到评测集 → 自动回归 |
| 6 | **安全护栏** | 输出护栏（guardrails）、内容审核、注入防护升级（LLM 判定 + 规则双层）、细粒度数据权限 |
| 7 | **A/B 与灰度** | 检索策略/模型版本可灰度发布，可回滚 |

### 4.3 P2 —— 多模态智能体演进（1~3 月）

**目标：从「RAG 问答」升级为「多模态 + Agent 工作流」。**

| # | 任务 | 技术要点 |
|---|------|---------|
| 1 | **多模态解析** | 图片/PDF 图文用视觉模型（Qwen2.5-VL）替代 PaddleOCR，输出「图文描述 + 表格结构化」；详见已有《Multimodal_RAG_Design.md》 |
| 2 | **多模态检索** | 文本向量 + 图像向量（视觉 embedding/CLIP）双通道，chunk 关联原始图片/页面坐标 |
| 3 | **Agent 工具调用** | 引入工具（查知识库/查工单/查日志/提交工单），ReAct 规划，多轮记忆 |
| 4 | **售后闭环** | 诊断 → 排查 → 工单 → 转人工，从问答升级为工作流 |
| 5 | **知识自更新** | 从问答与工单中自动抽取 FAQ，反哺知识库 |

---

## 5. 关键技术选型对比

| 能力 | 当前 | P0 建议 | P2 建议 |
|------|------|--------|--------|
| 关键词检索 | Python 全量扫描 BM25 | PostgreSQL `tsvector`+`zhparser`（零新组件） | Elasticsearch（吞吐更大时） |
| 向量检索 | pgvector HNSW | pgvector HNSW + 元数据过滤 | 多向量（文本+图像） |
| 重排序 | 未启用 | `bge-reranker-large` | `bge-reranker-v2-m3`（多语言更强） |
| 切片 | 递归字符切分 | 结构感知 + 父子分块 | 多模态 chunk（图/文/表/坐标） |
| 清洗 | 正则 + 关键词 | 可配置规则管线 + 保留语义的 PII 策略 | LLM 辅助清洗 |
| 任务队列 | Redis Stream（轻量） | Redis Stream + DLQ + 状态机 | Celery/RQ（需水平扩展时） |
| 评测 | 无 | 评测集 + RAGAS | 在线 A/B + 持续回归 |
| 推理 | Ollama | Ollama（单机） | vLLM（并发吞吐） |

---

## 6. 多模态智能体架构演进路径

```
现在：RAG 问答（单轮）
  → P0：企业级检索管线（漏斗 + 评测 + 可观测）
  → P1：智能检索（查询理解 + 缓存 + 反馈闭环 + 安全护栏）
  → P2.1：多模态（视觉模型 + 图文检索 + 表格结构化）
  → P2.2：Agent（工具调用 + 规划 + 多轮记忆 + 售后工作流闭环）
```

**关键不变式（避免推倒重来）：**
1. **检索与生成解耦**：检索返回「结构化 chunk + 元数据 + 分数」，生成层只消费该结构，Agent 阶段可直接复用。
2. **chunk 作为一等公民**：所有 chunk 带 `document_id / heading_path / content_type / chunk_meta`，无论文本还是多模态都走同一套检索/评测。
3. **可观测贯穿始终**：每个请求带 TraceID，检索每个阶段记录耗时与命中，评测可回溯。

---

## 7. 迁移与风险控制

1. **向量维度迁移（768 → 1024）**：先写迁移脚本，新文档用新维度 + 新列 `embedding_v2`，双写灰度，检索侧按模型版本路由，旧数据后台渐进重算，验证后切换。
2. **切片策略变更需重建索引**：父子分块、结构感知会改变 chunk 边界，需一次性重建，保留旧版本以便回滚。
3. **清洗策略变更会改变知识内容**：PII 策略从「脱敏」改为「保留 + 审计」，避免误伤售后示例值。
4. **灰度与回滚**：检索策略、模型、prompt 均做成可配置 + 可灰度，任何上线保留回滚开关。

---

## 8. 优先级建议与下一步

**强烈建议按 P0 → P1 → P2 顺序推进，先做 P0 里「投入小、收益大」的 4 件事：**

1. `chat.py` 复用连接池（30 分钟，立刻见效）。
2. 入库批处理 + 去 `sleep`（半天，入库提速 5~10 倍）。
3. BM25 索引化（1 天，检索性能与质量双提升）。
4. 切片父子分块 + 元数据（1~2 天，根治长文档「只覆盖一半」，同时为多模态打地基）。

> 以上每项都可独立交付、独立回滚。建议逐项实施，每项实施后配合评测集验证「召回率/忠实度」是否有提升，避免「改了但说不清好坏」。

---

## 附：与现有文档的关系

- 本文是《网站群售后助手-架构设计.md》的「检索/AI 能力」深化，不替代其整体架构。
- 多模态解析细节复用《Multimodal_RAG_Design.md》，本文只负责「检索与 Agent 演进」部分。
- 微调/数据集相关工作见《Qwen_RAG_FineTuning_Design.md》，本文未涉及（检索优先，微调后置）。
