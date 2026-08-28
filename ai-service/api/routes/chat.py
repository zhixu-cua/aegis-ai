import json
import os
import re
import time
import urllib.error
import urllib.request
import asyncpg
import asyncio
import math
import httpx

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from api.db import get_pool
from api.tokenizer import tokenize
from api.logging_utils import get_logger, set_request_id
import uuid

log = get_logger("rag")

# ---------- 重排序模型（可选依赖） ----------
try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None

router = APIRouter()

# ============================================================================
# 可配置参数（全部支持环境变量覆盖，方便后续切换中文向量模型 / 重排模型）
# ============================================================================
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.8:27b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5433"))
DB_NAME = os.getenv("DB_NAME", "aegis_assistant")
DB_USER = os.getenv("DB_USER", "aegis")
DB_PASSWORD = os.getenv("DB_PASSWORD", "aegis123")

VECTOR_TOP_K = int(os.getenv("VECTOR_TOP_K", "100"))            # 向量检索候选数
BM25_TOP_K = int(os.getenv("BM25_TOP_K", "100"))                # 关键词检索候选数
BM25_CORPUS_LIMIT = int(os.getenv("BM25_CORPUS_LIMIT", "10000"))# BM25 全语料上限（防止超大库 OOM）
RERANK_CANDIDATE_K = int(os.getenv("RERANK_CANDIDATE_K", "30")) # 进入重排的候选数
FINAL_TOP_K = int(os.getenv("FINAL_TOP_K", "10"))                # 最终喂给 LLM 的核心片段数
RERANK_MIN_SCORE = float(os.getenv("RERANK_MIN_SCORE", "0.0"))
# 每个核心片段向两侧扩展的相邻块数（长文档切片后，相邻块常包含答案的完整上下文）
NEIGHBOR_WINDOW = int(os.getenv("NEIGHBOR_WINDOW", "1"))
# 是否尝试调用 Ollama /api/tokenize 精确计数（部分 Ollama 版本缺少该接口，默认关闭以避免 404 告警）
TOKENIZE_API_ENABLED = os.getenv("TOKENIZE_API", "0") == "1"

# ---------- 新增：动态上下文窗口相关参数 ----------
MAX_CTX = int(os.getenv("MAX_CTX", "32768"))        # 硬上限（防止显存溢出）
MIN_CTX = int(os.getenv("MIN_CTX", "4096"))         # 最小上下文（兜底）
CTX_BUFFER = int(os.getenv("CTX_BUFFER", "2048"))   # 额外预留 Buffer（给系统提示词和输出留空间）
# 若无法精确计算 Token，使用字符数估算（中英文混合场景 1 字符 ≈ 1.6 Token）
ESTIMATE_RATIO = float(os.getenv("ESTIMATE_RATIO", "1.6"))

# ============================================================================
# 重排序配置
# ============================================================================
# 重排序模式：
#   remote                —— 调用远程「重排微服务」（推荐，重排跑在远程 GPU 服务器上，本地零资源）
#   sentence_transformers —— 在本机加载 sentence-transformers 模型（仅当本机有 GPU 时用）
#   off                   —— 关闭重排序，直接使用 RRF 融合结果
RERANK_MODE = os.getenv("RERANK_MODE", "remote")
# 远程重排微服务地址（在远程 GPU 服务器上部署 rerank-service，见 rerank-service/README.md）
RERANK_API_URL = os.getenv("RERANK_API_URL", "http://127.0.0.1:8001")
# 重排模型名（透传给远程服务，用于日志/展示；实际由远程服务自身配置）
RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
# 重排相关性阈值：最高分低于该值视为无有效知识（bge-reranker 输出 logits，>0 即相关）
RERANK_MIN_SCORE = float(os.getenv("RERANK_MIN_SCORE", "0.0"))

# 本地 sentence-transformers（仅 RERANK_MODE=sentence_transformers 时使用，需本机 GPU）
try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None

_local_reranker = None

def _get_local_reranker():
    """懒加载本地 cross-encoder（仅 sentence_transformers 模式调用，默认不占用本地资源）。"""
    global _local_reranker
    if _local_reranker is not None or CrossEncoder is None:
        return _local_reranker
    models = [m.strip() for m in os.getenv("RERANKER_MODELS", "BAAI/bge-reranker-large").split(",") if m.strip()]
    for model_name in models:
        for device in ("cuda", "cpu"):
            try:
                kwargs = {"device": device, "max_length": 512}
                try:
                    _local_reranker = CrossEncoder(model_name, **kwargs)
                except TypeError:
                    kwargs.pop("trust_remote_code", None)
                    _local_reranker = CrossEncoder(model_name, **kwargs)
                log.info(f"本地重排模型加载成功: {model_name} on {device}")
                return _local_reranker
            except Exception as e:
                print(f"Warning: 加载本地重排模型失败 {model_name} on {device}: {e}")
    return None


async def _rerank_candidates(question: str, candidate_rows: List[Dict[str, Any]]):
    """
    对候选片段重排序。
    返回 (按相关性降序的 rows, 最高分)；失败或关闭时保持 RRF 顺序。
    """
    if len(candidate_rows) <= 1:
        return candidate_rows, RERANK_MIN_SCORE

    if RERANK_MODE == "remote":
        return await _rerank_via_remote(question, candidate_rows)
    if RERANK_MODE == "sentence_transformers":
        local = _get_local_reranker()
        if local is not None:
            return _rerank_via_sentence_transformers(local, question, candidate_rows)
    # off / 失败：保持 RRF 顺序
    return candidate_rows, RERANK_MIN_SCORE


async def _rerank_via_remote(question: str, candidate_rows: List[Dict[str, Any]]):
    """
    调用远程「重排微服务」（部署在 GPU 服务器，见 rerank-service/）。
    请求体: {"query": ..., "documents": [...]}
    响应体: {"model": ..., "results": [{"index": 0, "relevance_score": 0.9}, ...]}
    失败时退化为 RRF 顺序。
    """
    try:
        docs = [row["chunk_text"] for row in candidate_rows]
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{RERANK_API_URL}/rerank",
                json={"model": RERANK_MODEL, "query": question, "documents": docs},
            )
            resp.raise_for_status()
            data = resp.json()
        results = data.get("results") or []
        idx_to_id = {i: row["id"] for i, row in enumerate(candidate_rows)}
        score_map = {}
        for r in results:
            idx = r.get("index")
            if idx is not None and idx in idx_to_id:
                score_map[idx_to_id[idx]] = float(r.get("relevance_score", 0.0))
        top = max(score_map.values()) if score_map else RERANK_MIN_SCORE
        ordered = sorted(candidate_rows, key=lambda row: score_map.get(row["id"], 0.0), reverse=True)
        return ordered, top
    except Exception as e:
        log.warning(f"远程重排失败，退化为 RRF 顺序: {e}")
        return candidate_rows, RERANK_MIN_SCORE


def _rerank_via_sentence_transformers(local_reranker, question: str, candidate_rows: List[Dict[str, Any]]):
    pairs = [[question, row["chunk_text"]] for row in candidate_rows]
    scores = local_reranker.predict(pairs)
    scored = sorted(zip(candidate_rows, scores), key=lambda x: float(x[1]), reverse=True)
    top = float(scored[0][1]) if scored else RERANK_MIN_SCORE
    return [row for row, _ in scored], top

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
        return f"chunk.document_id IN (SELECT id FROM kb_document WHERE datasource_id = ${base})", [request.datasourceId]

    if request.tenantId is not None:
        try:
            user_id_int = int(request.tenantId)
        except (TypeError, ValueError):
            user_id_int = -1
        clause = (
            f"chunk.document_id IN (SELECT id FROM kb_document WHERE upload_user_id = ${base} OR datasource_id IN ("
            f"SELECT id FROM kb_datasource WHERE tenant_id = ${base + 1} OR is_shared = true"
            f"))"
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


async def _bm25_search(conn, query_tokens, request: QueryRequest) -> List[int]:
    """
    基于倒排索引 kb_chunk_terms 的 BM25 检索（只检索子块）。
    倒排索引为空（尚未重建索引）时，回退为全语料扫描。
    """
    if not query_tokens:
        return []

    terms_count = await conn.fetchval("SELECT COUNT(*) FROM kb_chunk_terms")
    if terms_count:
        # 统计 N 与 avgdl（过滤后语料，仅含向量的子块）
        n_filter, n_params = _build_filter(request, base=1)
        n_cond = f"AND {n_filter}" if n_filter else ""
        n_avgdl = await conn.fetchrow(f"""
            SELECT COUNT(*)::float AS n, COALESCE(AVG(LENGTH(chunk.chunk_text)), 0)::float AS avgdl
            FROM kb_chunk chunk
            WHERE chunk.embedding IS NOT NULL {n_cond}
        """, *n_params)
        N = float(n_avgdl["n"]) or 0.0
        avgdl = float(n_avgdl["avgdl"]) or 0.0
        if N <= 0 or avgdl <= 0:
            return []

        bm25_filter, bm25_params = _build_filter(request, base=2)
        bm25_cond = f"AND {bm25_filter}" if bm25_filter else ""
        bm25_query = f"""
            SELECT t.chunk_id AS id,
                   SUM(
                     (LN(1 + (({N} - df.cnt + 0.5) / (df.cnt + 0.5)))) *
                     ((t.tf * (1.5 + 1)) / (t.tf + 1.5 * (1 - 0.75 + 0.75 * LENGTH(chunk.chunk_text) / {avgdl})))
                   ) AS score
            FROM kb_chunk_terms t
            JOIN (SELECT term, COUNT(*)::float AS cnt FROM kb_chunk_terms GROUP BY term) df ON df.term = t.term
            JOIN kb_chunk chunk ON chunk.id = t.chunk_id
            WHERE t.term = ANY($1::text[])
              AND chunk.embedding IS NOT NULL
              {bm25_cond}
            GROUP BY t.chunk_id
            ORDER BY score DESC
            LIMIT {BM25_TOP_K}
        """
        rows = await conn.fetch(bm25_query, query_tokens, *bm25_params)
        return [row["id"] for row in rows]

    # 回退：倒排索引为空，退化为全语料扫描（与旧实现一致）
    fb_filter, fb_params = _build_filter(request, base=1)
    fb_cond = f"AND {fb_filter}" if fb_filter else ""
    fb_query = f"""
        SELECT chunk.id, chunk.chunk_text
        FROM kb_chunk chunk
        WHERE chunk.embedding IS NOT NULL {fb_cond}
        LIMIT {BM25_CORPUS_LIMIT}
    """
    fb_rows = await conn.fetch(fb_query, *fb_params)
    if not fb_rows:
        return []
    corpus = [tokenize(row["chunk_text"]) for row in fb_rows]
    bm25 = SimpleBM25(corpus)
    bm25_scores = bm25.get_scores(query_tokens)
    bm25_ranked = sorted(
        zip([row["id"] for row in fb_rows], bm25_scores),
        key=lambda x: x[1],
        reverse=True,
    )
    return [cid for cid, s in bm25_ranked if s > 0][:BM25_TOP_K]


async def _expand_parents(conn, selected_rows) -> List[Dict[str, Any]]:
    """
    small-to-big：用命中子块的父块（完整章节）作为回答上下文；
    若子块无父块（旧数据），则保留子块本身。父块不参与检索，仅作上下文。
    """
    parent_ids = {row["parent_id"] for row in selected_rows if row.get("parent_id")}
    if not parent_ids:
        return selected_rows

    parents = await conn.fetch("""
        SELECT chunk.id, chunk.document_id, chunk.chunk_index, chunk.chunk_text,
               chunk.section_title, chunk.heading_path, chunk.parent_id
        FROM kb_chunk chunk
        WHERE chunk.id = ANY($1::bigint[])
    """, list(parent_ids))
    parent_map = {row["id"]: row for row in parents}

    result: List[Dict[str, Any]] = []
    seen = set()
    for row in selected_rows:
        pid = row.get("parent_id")
        p = parent_map.get(pid) if pid else None
        target = p if p is not None else row
        if target["id"] not in seen:
            seen.add(target["id"])
            result.append(target)
    return result

# ============================================================================
# 计算 Token 数的辅助函数
# ============================================================================
def _est_tokens(text: str) -> int:
    """快速估算 token 数（不做 HTTP 调用，用于上下文截断与 num_ctx 计算）：
    中日韩文字按 1 字符 ≈ 1 token 估算，其余字符按 4 字符 ≈ 1 token 估算。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    other = len(text) - cjk
    return cjk + (other + 3) // 4


_tokenize_warned = False

def count_tokens(text: str, model: str = None) -> int:
    """
    计算 Token 数。

    默认使用本地估算（不调用 Ollama），避免部分 Ollama 版本缺少
    /api/tokenize 接口时每次都抛出 “HTTP Error 404” 告警。
    若设置环境变量 TOKENIZE_API=1，则优先调用 Ollama /api/tokenize 精确计算，
    失败时静默回退到本地估算（仅首次打印告警，避免刷屏）。
    """
    global _tokenize_warned
    if not text:
        return 0

    if TOKENIZE_API_ENABLED:
        tokenize_url = f"{OLLAMA_BASE_URL}/api/tokenize"
        payload = {
            "model": model or LLM_MODEL,
            "prompt": text,  # /api/tokenize 的请求字段名是 prompt，不是 content
        }
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        try:
            req = urllib.request.Request(
                tokenize_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with opener.open(req, timeout=10.0) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                tokens = result.get("tokens")
                if isinstance(tokens, list):
                    return len(tokens)
                if "count" in result:
                    return int(result["count"])
        except Exception as e:
            if not _tokenize_warned:
                print(f"Warning: Tokenize API 不可用，改用本地估算: {e}")
                _tokenize_warned = True

    # 本地估算（更贴近 qwen 中文分词，且不会产生告警）
    return _est_tokens(text)


def _truncate_context(chunks: List[str], max_tokens: int) -> List[str]:
    """按 Token 预算截断上下文，避免超长上下文被 Ollama 静默截断导致内容丢失。"""
    if max_tokens <= 0:
        return chunks
    kept: List[str] = []
    used = 0
    for c in chunks:
        t = _est_tokens(c)
        if kept and used + t > max_tokens:
            break
        kept.append(c)
        used += t
    return kept

# ============================================================================
# 主接口
# ============================================================================
def _embed_question(question: str):
    """同步生成问题向量（在 asyncio.to_thread 中运行，避免阻塞事件循环）。"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    embed_req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        data=json.dumps({"model": EMBEDDING_MODEL, "prompt": question}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with opener.open(embed_req, timeout=300.0) as response:
        result = json.loads(response.read().decode("utf-8"))
        embedding = result.get("embedding")
        if not embedding:
            raise Exception("Failed to generate embedding for question")
        return embedding


@router.post("/internal/rag/query")
async def rag_query(request: QueryRequest):
    set_request_id(uuid.uuid4().hex[:12])

    # 1. 生成问题向量（在独立线程中执行阻塞的 HTTP 调用）
    try:
        question_embedding = await asyncio.to_thread(_embed_question, request.question)
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
            pool = get_pool()
            if pool is not None:
                conn = await pool.acquire()
                should_close = False
            else:
                conn = await asyncpg.connect(
                    host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
                )
                should_close = True
            try:
                # --- 2.1 向量检索（只检索有向量的子块，排除父块） ---
                vector_filter, vector_params = _build_filter(request, base=2)
                vector_condition = f"AND {vector_filter}" if vector_filter else ""
                vector_query = f"""
                    SELECT chunk.id, chunk.document_id, chunk.chunk_index, chunk.chunk_text,
                           chunk.section_title, chunk.heading_path, chunk.parent_id,
                           1 - (chunk.embedding <=> $1::vector) AS vector_score
                    FROM kb_chunk chunk
                    WHERE chunk.embedding IS NOT NULL
                    {vector_condition}
                    ORDER BY vector_score DESC
                    LIMIT {VECTOR_TOP_K}
                """
                vector_rows = await conn.fetch(vector_query, str(question_embedding), *vector_params)
                if not vector_rows:
                    return []
                vector_ranked_ids = [row["id"] for row in vector_rows]

                # --- 2.2 关键词 BM25（倒排索引） ---
                query_tokens = tokenize(request.question)
                bm25_ranked_ids = await _bm25_search(conn, query_tokens, request)

                # --- 2.3 RRF 融合 ---
                rrf_scores = compute_rrf(vector_ranked_ids, bm25_ranked_ids, k=60)
                fused_ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
                if not fused_ranked:
                    return []

                # 取前 RERANK_CANDIDATE_K 个候选，一次性获取完整行
                candidate_ids = [cid for cid, _ in fused_ranked[:RERANK_CANDIDATE_K]]
                candidate_rows = await conn.fetch("""
                    SELECT chunk.id, chunk.document_id, chunk.chunk_index, chunk.chunk_text,
                           chunk.section_title, chunk.heading_path, chunk.parent_id
                    FROM kb_chunk chunk
                    WHERE chunk.id = ANY($1::bigint[])
                """, candidate_ids)
                row_map = {row["id"]: row for row in candidate_rows}
                candidate_rows_ordered = [row_map[cid] for cid in candidate_ids if cid in row_map]
                if not candidate_rows_ordered:
                    return []

                # --- 2.4 重排序（远程 Ollama /api/rerank 或本地 sentence-transformers） ---
                reranked_rows, top_score = await _rerank_candidates(request.question, candidate_rows_ordered)
                if top_score < RERANK_MIN_SCORE:
                    # 最高分低于阈值：视为无有效知识，退回闲聊兜底
                    return []
                selected_rows = reranked_rows[:FINAL_TOP_K]

                # --- 2.5 父子块上下文扩展（small-to-big） ---
                selected_rows = await _expand_parents(conn, selected_rows)

                # --- 2.6 组装上下文（去重 + 同文档相邻去重叠） ---
                return _build_context(selected_rows)

            finally:
                try:
                    if should_close:
                        await conn.close()
                    else:
                        await pool.release(conn)
                except ConnectionAbortedError:
                    pass
                except Exception:
                    pass

        chunks_text = await _query_db()
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Hybrid search failed: {str(e)}")

    # ========================================================================
    # 3. 构造 RAG Prompt
    # ========================================================================
    # 先计算输出长度与上下文 Token 预算，并在构造 prompt 前截断上下文，
    # 避免超长上下文被 Ollama 静默截断（那会导致回答只覆盖到部分内容）
    num_predict = int(os.getenv("NUM_PREDICT", "4096"))
    max_context_tokens = max(0, MAX_CTX - CTX_BUFFER - num_predict)
    chunks_text = _truncate_context(chunks_text, max_context_tokens)
    context = "\n\n".join(chunks_text)

    if context.strip():
        prompt = (
            "你是一名专业的售后客服助手。请严格依据下方【参考资料】回答用户问题。\n\n"
            "【回答要求】\n"
            "1. 只使用与用户问题直接相关的资料内容；若某些资料与问题无关，请直接忽略，绝不生硬拼凑或缝合。\n"
            "2. 回答必须完整、全面：把参考资料中所有与问题相关的要点、步骤、原因和注意事项都覆盖到，不要遗漏，也不要只挑部分内容作答。\n"
            "3. 先给出明确结论，再分点详细说明，必要时给出示例；不要只回一句空话，也不要中途省略或截断。\n"
            "4. 若资料不足以完全回答，可结合你的通用知识补充，但必须说明哪些来自资料、哪些是你的补充；若确实无法回答，请如实说明，并给出可操作的排查建议。\n"
            "5. 使用简体中文，可适度使用 Markdown（标题/列表/表格）提升可读性，但段落之间不要堆砌多余空行。\n\n"
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

    # ========================================================================
    # 4. 动态计算 num_ctx
    # ========================================================================
    # 计算 prompt 的 Token 数（精确计算，失败则估算；在独立线程执行避免阻塞）
    prompt_tokens = await asyncio.to_thread(count_tokens, prompt, LLM_MODEL)

    # 动态设置 num_ctx = prompt_tokens + 预留输出长度（取 num_predict 和 CTX_BUFFER 的较大值）
    # 但必须限制在 [MIN_CTX, MAX_CTX] 之间
    dynamic_ctx = prompt_tokens + max(num_predict, CTX_BUFFER)
    final_ctx = max(MIN_CTX, min(MAX_CTX, dynamic_ctx))

    log.info(f"动态上下文: prompt_tokens={prompt_tokens}, num_predict={num_predict}, "
             f"动态值={dynamic_ctx}, 最终={final_ctx} (MIN={MIN_CTX}, MAX={MAX_CTX})")

    # 5. 调用 LLM 流式生成（使用动态计算出的 final_ctx）
    ollama_url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": True,
        "keep_alive": "10m",
        "options": {
            "num_predict": num_predict,
            "num_ctx": final_ctx,                       # 动态设置
            "temperature": float(os.getenv("TEMPERATURE", "0.3")),
            "top_p": float(os.getenv("TOP_P", "0.8")),
            "repeat_penalty": float(os.getenv("REPEAT_PENALTY", "1.1")),
        },
    }

    def generate_stream():
        # 显式绕过系统代理，避免本地服务请求被代理软件干扰
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
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