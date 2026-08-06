# 多模态文件解析与 RAG 系统融合设计方案

为了让 Aegis AI 系统支持上传并解析 Word (`.docx`, `.doc`)、Excel (`.xlsx`, `.xls`)、PDF (`.pdf`) 以及图片 (`.png`, `.jpg`) 等多种格式文件，我们需要在现有的 RAG 架构中引入一个专门的 **文档 ETL（提取、转换、加载）处理流水线**。

该方案将解析压力集中在生态更丰富的 Python (FastAPI) 端，通过异步任务队列保障系统稳定性。

---

## 一、 系统架构数据流设计

1. **前端 (Vue3)**
   - 开放 `<input type="file" accept=".txt,.md,.pdf,.docx,.doc,.xlsx,.xls,.png,.jpg">` 限制。
   - 文件上传时，展示“文件解析中”的进度状态（UI 层面可做轮询或接收 WebSocket/SSE 通知）。
2. **后端网关 (Java Spring Boot)**
   - 接收前端上传的文件流，将物理文件存储至服务器本地磁盘或对象存储（如 MinIO/OSS）。
   - 在 `kb_document` 数据库表中生成一条记录，状态标记为 `PARSING` (解析中)。
   - **异步触发**：通过 HTTP 请求将文件物理路径（或下载 URL）及文档 ID 传递给 Python 端的解析接口。
3. **AI 算法端 (Python FastAPI)**
   - 接收解析任务，启动后台异步任务（使用 FastAPI 的 `BackgroundTasks` 或引入 `Celery`）。
   - **分发器 (Router)**：根据文件扩展名，将任务路由至不同的解析引擎。
   - **处理管线 (Pipeline)**：提取文本 -> 文本清洗 -> 智能分块 (Chunking) -> 向量化 (Embedding) -> 存入 PostgreSQL (`kb_chunk`)。
   - **回调 (Callback)**：处理完成后，回调 Java 接口，将 `kb_document` 的状态更新为 `READY` 或 `FAILED`。

---

## 二、 核心解析引擎技术选型与处理策略

在 Python 端，我们将构建一个解析工厂 `DocumentParserFactory`，集成以下开源库：

### 1. PDF 文件 (`.pdf`)
*   **依赖库**: `pdfplumber` 或 `PyMuPDF (fitz)`。
*   **处理策略**:
    *   遍历 PDF 的每一页，提取纯文本。
    *   **难点（表格）**: 使用 `pdfplumber.extract_tables()` 识别页面内的表格，将其转换为 Markdown 格式 (`| 列1 | 列2 |`) 并插入到正文中。如果表格被强行转为一维纯文本，大模型将丧失对行列逻辑的理解。

### 2. Word 文件 (`.doc`, `.docx`)
*   **依赖库**: `python-docx`。如果是老旧的二进制 `.doc` 格式，需在服务器安装 `LibreOffice`，通过 Python 脚本调用 `soffice --headless --convert-to docx` 将其预处理为 `.docx`。
*   **处理策略**:
    *   遍历文档的 `paragraphs` 提取文本。
    *   遍历文档的 `tables` 提取表格数据，同样转换为 Markdown 表格格式。
    *   保留文档原本的标题（Heading 1, 2, 3...），在后续 Chunking 阶段可作为分块边界。

### 3. Excel 文件 (`.xlsx`, `.xls`)
*   **依赖库**: `pandas` + `openpyxl` (针对 xlsx) + `xlrd` (针对 xls)。
*   **处理策略**:
    *   **绝对禁止**按传统的字符数盲目截断，这会导致数据错乱。
    *   **策略 A (行序列化)**: 遍历每一行，结合表头转化为自然语言描述。例如表头是“姓名”、“故障”，内容是“张三”、“无法开机”，则转化为：`记录：姓名为张三，故障为无法开机。`
    *   **策略 B (Markdown 转换)**: 若表格不宽，使用 `pandas.DataFrame.to_markdown()` 直接转为 Markdown 表格存入块中。

### 4. 图片文件 (`.png`, `.jpg`)
*   **依赖库**: `PaddleOCR`。
*   **处理策略**:
    *   引入百度开源的 PaddleOCR，对图片进行光学字符识别。
    *   提取出带有坐标边界框的文本片段。
    *   编写逻辑将文本框按“从上到下、从左到右”的阅读顺序重组拼接为连贯的段落。

---

## 三、 智能语义分块 (Chunking) 策略升级

多模态文档解析出的文本结构复杂，之前的简单按字数切分已不适用，需升级为 **LangChain 文本分割器**：

1. **对于普通段落 (Word, PDF 正文, OCR 结果)**：
   使用 `RecursiveCharacterTextSplitter`。优先按双换行 `\n\n` 切分（保证段落完整），其次按句号 `。` 切分（保证句子完整），最后才按字数硬切分。
2. **对于表格数据 (Markdown 表格)**：
   若表格极大，需自定义分割器，保证每次切分后的 Chunk 都**自动在头部带上该表格的表头信息**，否则模型检索到中间某块时将不知所云。

---

## 四、 系统资源与风险防范

1. **解析超时与阻塞**
   *   **风险**: OCR 识别或上百页的 PDF 解析是典型的 CPU/内存密集型任务。如果同步执行，会导致请求超时（504），甚至拖垮 FastAPI 的主事件循环。
   *   **方案**: 必须将解析动作放入**消息队列**（如 Redis + Celery）或 FastAPI 的 `BackgroundTasks` 中异步执行，彻底解耦。
2. **内存溢出 (OOM)**
   *   **风险**: `pandas` 读取巨大 Excel 或 `pdfplumber` 处理海量高清图片 PDF 时极耗内存。
   *   **方案**: Python 端限制单次解析的最大文件大小（如 50MB）。针对 PDF 采用迭代器 (Generator) 逐页读取并清理内存，而非一次性加载全书。
3. **混合排版丢失**
   *   **风险**: Word/PDF 中往往图文并茂，目前的纯文本解析库会漏掉图片里的关键信息。
   *   **方案 (进阶)**: 如果业务强依赖图文混合理解，未来可引入 `Qwen-VL` (视觉大模型) 替代 PaddleOCR。将文档页面转为图片喂给视觉模型，让其直接输出包含图表的完整文字描述。