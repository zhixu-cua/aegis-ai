import json
import os
import re
import time
import urllib.error
import urllib.request
import asyncpg
import asyncio
import math

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

# ---------- 中文分词 ----------
try:
    import jieba
    # 预热词典，避免首次调用时出现明显的阻塞
    try:
        jieba.initialize()
    except Exception:
        pass
except ImportError:
    jieba = None

# ---------- 重排序模型（可选依赖） ----------
try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None

router = APIRouter()


# ============================================================================
# 可配置参数（全部支持环境变量覆盖，方便后续切换中文向量模型 / 重排模型）
# ============================================================================
#EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5433"))
DB_NAME = os.getenv("DB_NAME", "aegis_assistant")
DB_USER = os.getenv("DB_USER", "aegis")
DB_PASSWORD = os.getenv("DB_PASSWORD", "aegis123")

VECTOR_TOP_K = int(os.getenv("VECTOR_TOP_K", "100"))            # 向量检索候选数
BM25_TOP_K = int(os.getenv("BM25_TOP_K", "100"))                # 关键词检索候选数
BM25_CORPUS_LIMIT = int(os.getenv("BM25_CORPUS_LIMIT", "10000"))# BM25 全语料上限（防止超大库 OOM）
RERANK_CANDIDATE_K = int(os.getenv("RERANK_CANDIDATE_K", "20")) # 进入重排的候选数
FINAL_TOP_K = int(os.getenv("FINAL_TOP_K", "5"))                # 最终喂给 LLM 的片段数
# 重排分数（原始 logit）阈值：低于该值的候选视为无关被丢弃；全部低于阈值则退回闲聊兜底
RERANK_MIN_SCORE = float(os.getenv("RERANK_MIN_SCORE", "0.0"))


# ============================================================================
# 重排序模型加载
# ============================================================================
# 前面。这里改用真正的交叉编码器(cross-encoder)，并增加 CUDA -> CPU 的回退。
_RERANKER_MODELS = [
    m.strip()
    for m in os.getenv(
        "RERANKER_MODELS",
        "BAAI/bge-reranker-large,BAAI/bge-reranker-base",
    ).split(",")
    if m.strip()
]


def _load_reranker():
    if CrossEncoder is None:
        print("Info: sentence-transformers 未安装，跳过重排序（使用 RRF 融合结果）。")
        return None
    for model_name in _RERANKER_MODELS:
        for device in ("cuda", "cpu"):
            try:
                kwargs = {"device": device, "max_length": 512}
                if "reranker-v2" in model_name or "m3" in model_name:
                    kwargs["trust_remote_code"] = True
                try:
                    reranker = CrossEncoder(model_name, **kwargs)
                except TypeError:
                    kwargs.pop("trust_remote_code", None)
                    reranker = CrossEncoder(model_name, **kwargs)
                print(f"Reranker loaded: {model_name} on {device}")
                return reranker
            except Exception as e:
                print(f"Warning: Failed to load reranker {model_name} on {device}: {e}")
    print("Warning: 所有重排模型加载失败，将退化为 RRF 融合结果。")
    return None


reranker = _load_reranker()


class QueryRequest(BaseModel):
    question: str
    datasourceId: Optional[int] = None
    tenantId: Optional[str] = None


# ============================================================================
# BM25 / RRF / 分词
# ============================================================================
class SimpleBM25:
    def __init__(self, corpus):
        self.corpus_size = len(corpus)
        self.avgdl = sum(len(doc) for doc in corpus) / self.corpus_size if self.corpus_size else 0
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        self.k1 = 1.5
        self.b = 0.75

        for document in corpus:
            self.doc_len.append(len(document))
            frequencies = {}
            for word in document:
                frequencies[word] = frequencies.get(word, 0) + 1
            self.doc_freqs.append(frequencies)
            for word in frequencies.keys():
                self.idf[word] = self.idf.get(word, 0) + 1

        for word, freq in self.idf.items():
            self.idf[word] = math.log(1 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def get_scores(self, query):
        scores = [0.0] * self.corpus_size
        for q in query:
            if q not in self.idf:
                continue
            idf = self.idf[q]
            for i, freqs in enumerate(self.doc_freqs):
                if q in freqs:
                    freq = freqs[q]
                    num = freq * (self.k1 + 1)
                    den = freq + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                    scores[i] += idf * num / den
        return scores


def _tokenize(text: str) -> List[str]:
    """中文优先使用 jieba 分词；缺失时退回字符 + 二元词组，避免退化成单字匹配。"""
    if jieba is not None:
        return [t for t in jieba.cut(text) if t.strip()]
    tokens: List[str] = []
    tokens.extend(re.findall(r"[a-zA-Z0-9_]+", text))
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        tokens.extend(run)
        tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    return tokens


def compute_rrf(rank_list1, rank_list2, k=60):
    rrf_scores = {}
    for rank, doc_id in enumerate(rank_list1):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

    for rank, doc_id in enumerate(rank_list2):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

    return rrf_scores


# ============================================================================
# 检索辅助函数
# ============================================================================
def _build_filter(request: QueryRequest, base: int):
    """
    构造 WHERE 过滤条件（不含 "WHERE" 关键字），并返回参数列表。
    base 为占位符起始编号：向量查询中 $1 是 embedding，所以 base=2；BM25 查询中 base=1。
    """
    if request.datasourceId is not None:
        return f"doc.datasource_id = ${base}", [request.datasourceId]

    if request.tenantId is not None:
        try:
            user_id_int = int(request.tenantId)
        except (TypeError, ValueError):
            user_id_int = -1
        clause = (
            f"doc.upload_user_id = ${base} OR doc.datasource_id IN ("
            f"SELECT id FROM kb_datasource WHERE tenant_id = ${base + 1} OR is_shared = true"
            f")"
        )
        return clause, [user_id_int, str(request.tenantId)]

    return "", []


def _find_overlap(prev_text: str, next_text: str, max_overlap: int = 300) -> int:
    """返回 prev_text 尾部与 next_text 头部重叠的字符数，无重叠返回 0。"""
    n = min(len(prev_text), len(next_text), max_overlap)
    for i in range(n, 0, -1):
        if prev_text.endswith(next_text[:i]):
            return i
    return 0


def _build_context(rows: List[Dict[str, Any]]) -> List[str]:
    """
    将选中的片段组装为最终上下文：
    1. 完全相同的文本去重；
    2. 按（文档、块序号）排序，保证同文档内顺序正确；
    3. 仅对“同一文档且块序号相邻”的片段做首尾重叠合并，绝不跨文档拼接。
    """
    # 去重（保留首次出现的行）
    seen = set()
    unique = []
    for row in rows:
        text = (row.get("chunk_text") or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        unique.append(row)

    # 排序：文档 + 块序号（chunk_index 缺失时退化为 0）
    unique.sort(key=lambda x: (x.get("document_id") or 0, x.get("chunk_index") or 0))

    merged: List[Dict[str, Any]] = []
    for row in unique:
        text = (row.get("chunk_text") or "").strip()
        if not text:
            continue
        if not merged:
            merged.append(row)
            continue

        prev = merged[-1]
        same_doc = (prev.get("document_id") == row.get("document_id"))
        adjacent = (
            (prev.get("chunk_index") is not None)
            and (row.get("chunk_index") is not None)
            and (row.get("chunk_index") == prev.get("chunk_index") + 1)
        )
        if same_doc and adjacent:
            overlap = _find_overlap(prev["chunk_text"], text)
            if overlap > 0:
                merged[-1] = dict(prev)
                merged[-1]["chunk_text"] = prev["chunk_text"] + text[overlap:]
                continue
        merged.append(row)

    return [row["chunk_text"] for row in merged]


# ============================================================================
# 主接口
# ============================================================================
@router.post("/internal/rag/query")
def rag_query(request: QueryRequest):
    # 显式绕过系统代理，避免本地服务请求被代理软件干扰。
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)

    # 1. 生成问题向量
    ollama_embed_url = f"{OLLAMA_BASE_URL}/api/embeddings"
    embed_payload = {
        "model": EMBEDDING_MODEL,
        "prompt": request.question,
    }
    embed_req = urllib.request.Request(
        ollama_embed_url,
        data=json.dumps(embed_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with opener.open(embed_req, timeout=300.0) as response:
            result = json.loads(response.read().decode("utf-8"))
            question_embedding = result.get("embedding")
            if not question_embedding:
                raise Exception("Failed to generate embedding for question")
    except urllib.error.HTTPError as he:
        if he.code == 404:
            raise HTTPException(
                status_code=500,
                detail=f"Ollama 报错 404: 缺少向量模型。请在终端执行 'ollama pull {EMBEDDING_MODEL}'",
            )
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(he)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")

    # 2. 混合检索：向量检索 + 全语料 BM25，再 RRF 融合 + 交叉编码器重排
    chunks_text = []
    try:
        async def _query_db():
            conn = await asyncpg.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
            )
            try:
                # --- 2.1 向量检索 ---
                vector_filter, vector_params = _build_filter(request, base=2)
                vector_condition = f"WHERE {vector_filter}" if vector_filter else ""
                vector_query = f"""
                    SELECT chunk.id, chunk.document_id, chunk.chunk_index, chunk.chunk_text,
                           1 - (chunk.embedding <=> $1::vector) AS vector_score
                    FROM kb_chunk chunk
                    JOIN kb_document doc ON chunk.document_id = doc.id
                    {vector_condition}
                    ORDER BY vector_score DESC
                    LIMIT {VECTOR_TOP_K}
                """
                vector_rows = await conn.fetch(vector_query, str(question_embedding), *vector_params)
                if not vector_rows:
                    return []
                vector_ranked_ids = [row["id"] for row in vector_rows]

                # --- 2.2 关键词 BM25：在全语料上计算，而非只在向量 TopK 内计算 ---
                bm25_filter, bm25_params = _build_filter(request, base=1)
                bm25_condition = f"WHERE {bm25_filter}" if bm25_filter else ""
                bm25_query = f"""
                    SELECT chunk.id, chunk.document_id, chunk.chunk_index, chunk.chunk_text
                    FROM kb_chunk chunk
                    JOIN kb_document doc ON chunk.document_id = doc.id
                    {bm25_condition}
                    LIMIT {BM25_CORPUS_LIMIT}
                """
                bm25_rows = await conn.fetch(bm25_query, *bm25_params)

                bm25_ranked_ids: List[int] = []
                if bm25_rows:
                    corpus = [_tokenize(row["chunk_text"]) for row in bm25_rows]
                    query_tokens = _tokenize(request.question)
                    bm25 = SimpleBM25(corpus)
                    bm25_scores = bm25.get_scores(query_tokens)
                    bm25_ranked = sorted(
                        zip([row["id"] for row in bm25_rows], bm25_scores),
                        key=lambda x: x[1],
                        reverse=True,
                    )
                    # 只保留真正命中关键词的候选（score > 0），并截断到 TopK
                    bm25_ranked_ids = [cid for cid, s in bm25_ranked if s > 0][:BM25_TOP_K]

                # --- 2.3 RRF 融合 ---
                rrf_scores = compute_rrf(vector_ranked_ids, bm25_ranked_ids, k=60)
                fused_ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

                # 建立 id -> row 映射（向量与 BM25 结果合并）
                all_rows_map: Dict[int, Dict[str, Any]] = {}
                for row in vector_rows:
                    all_rows_map[row["id"]] = row
                for row in (bm25_rows or []):
                    all_rows_map.setdefault(row["id"], row)

                candidate_rows = []
                for doc_id, _ in fused_ranked[:RERANK_CANDIDATE_K]:
                    row = all_rows_map.get(doc_id)
                    if row is not None:
                        candidate_rows.append(row)

                if not candidate_rows:
                    return []

                # --- 2.4 交叉编码器重排 + 相关性过滤 ---
                selected_rows = candidate_rows
                if reranker is not None and len(candidate_rows) > 1:
                    pairs = [[request.question, row["chunk_text"]] for row in candidate_rows]
                    try:
                        scores = reranker.predict(pairs)
                        scored = sorted(
                            zip(candidate_rows, scores),
                            key=lambda x: float(x[1]),
                            reverse=True,
                        )
                        top_score = float(scored[0][1]) if scored else RERANK_MIN_SCORE
                        if top_score >= RERANK_MIN_SCORE:
                            selected_rows = [
                                row for row, s in scored if float(s) >= RERANK_MIN_SCORE
                            ][:FINAL_TOP_K]
                        else:
                            # 全部候选都低于相关性阈值：视为无有效知识，退回闲聊兜底
                            return []
                    except Exception as e:
                        print(f"Warning: 重排序失败，退化为 RRF TopK: {e}")
                        selected_rows = candidate_rows[:FINAL_TOP_K]
                else:
                    selected_rows = candidate_rows[:FINAL_TOP_K]

                # --- 2.5 组装上下文（去重 + 同文档相邻去重叠） ---
                return _build_context(selected_rows)

            finally:
                try:
                    await conn.close()
                except ConnectionAbortedError:
                    pass
                except Exception:
                    pass

        # 解决 Windows 下代理软件导致 asyncio IOCP 抛出 WinError 10038 的问题
        import sys
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        chunks_text = asyncio.run(_query_db())
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Hybrid search failed: {str(e)}")

    # 3. 构造 RAG Prompt
    context = "\n\n".join(chunks_text)

    if context.strip():
        prompt = (
            "你是一名专业的售后客服助手。请严格依据下方【参考资料】回答用户问题。\n\n"
            "【回答要求】\n"
            "1. 只使用与用户问题直接相关的资料内容；若某些资料与问题无关，请直接忽略，绝不生硬拼凑或缝合。\n"
            "2. 回答要完整、有条理、足够详细：先给出明确结论，再分点说明操作步骤、原因或注意事项，必要时给出示例；不要只回一句空话。\n"
            "3. 若资料不足以完全回答，可结合你的通用知识补充，但必须说明哪些来自资料、哪些是你的补充；若确实无法回答，请如实说明，并给出可操作的排查建议。\n"
            "4. 使用简体中文，可适度使用 Markdown（标题/列表/表格）提升可读性，但段落之间不要堆砌多余空行。\n\n"
            "【参考资料】\n"
            f"{context}\n\n"
            "【用户问题】\n"
            f"{request.question}"
        )
    else:
        prompt = (
            "你是一名专业的智能售后客服助手，请用简体中文回答用户问题。\n"
            "回答要完整、有条理：先给出结论，再分点说明；若问题超出你的专业范围，请委婉说明，并给出可行的排查方向。\n"
            "可适度使用 Markdown 提升可读性，但段落之间不要堆砌多余空行。\n\n"
            "【用户问题】\n"
            f"{request.question}"
        )

    # 4. 调用 LLM 流式生成
    ollama_url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": True,
        "keep_alive": "10m",
        "options": {
            "num_predict": int(os.getenv("NUM_PREDICT", "4096")),
            "num_ctx": int(os.getenv("NUM_CTX", "8192")),
            "temperature": float(os.getenv("TEMPERATURE", "0.3")),
            "top_p": float(os.getenv("TOP_P", "0.8")),
            "repeat_penalty": float(os.getenv("REPEAT_PENALTY", "1.1")),
        },
    }

    def generate_stream():
        emitted_any = False
        last_error = "未知错误"
        for attempt in range(3):
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    ollama_url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                )
                with opener.open(req, timeout=300.0) as response:
                    for raw in response:
                        if not raw:
                            continue
                        try:
                            chunk = json.loads(raw)
                        except (json.JSONDecodeError, ValueError):
                            continue
                        if chunk.get("response"):
                            emitted_any = True
                            yield chunk["response"]
                        if chunk.get("done"):
                            break
                if emitted_any:
                    return
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8", errors="ignore")
                last_error = f"HTTP {e.code}: {error_body or e.reason}"
            except Exception as e:
                last_error = str(e)

            # 只有在前一次完全没产出时才重试，避免已输出内容后又从头重来造成重复/错乱
            if attempt < 2 and not emitted_any:
                time.sleep(1)

        if not emitted_any:
            yield f"\n[抱歉，AI 服务暂时不可用，请稍后重试：{last_error}]"

    return StreamingResponse(generate_stream(), media_type="text/plain; charset=utf-8")
