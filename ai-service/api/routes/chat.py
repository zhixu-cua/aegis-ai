import json
import time
import urllib.error
import urllib.request
import asyncpg
import asyncio
import math

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    import jieba
except ImportError:
    jieba = None

try:
    from sentence_transformers import CrossEncoder
    # 初始化重排序模型 ms-marco-MiniLM-L-6-v2
    # 可以在此处调整模型路径或设备参数，例如 device='cpu' 或 device='cuda'
    reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
   # reranker = None # 暂时注释掉重排序，只用混合检索
except ImportError:
    reranker = None

router = APIRouter()

class QueryRequest(BaseModel):
    question: str

# 简单的 BM25 实现
class SimpleBM25:
    def __init__(self, corpus):
        self.corpus_size = len(corpus)
        self.avgdl = sum(len(doc) for doc in corpus) / self.corpus_size if self.corpus_size else 0
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        # BM25 可调参数: k1 (通常在 1.2~2.0 之间), b (通常在 0.75 左右)
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
    # RRF 融合参数: k (通常设置为 60)
    rrf_scores = {}
    for rank, doc_id in enumerate(rank_list1):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
        
    for rank, doc_id in enumerate(rank_list2):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
        
    return rrf_scores

@router.post("/internal/rag/query")
def rag_query(request: QueryRequest):
    # 显式绕过系统代理，避免本地服务请求被代理软件干扰。
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)

    # 1. Generate embedding for the question using nomic-embed-text
    ollama_embed_url = "http://127.0.0.1:11434/api/embeddings"
    embed_payload = {
        "model": "nomic-embed-text",
        "prompt": request.question
    }
    embed_req = urllib.request.Request(
        ollama_embed_url,
        data=json.dumps(embed_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with opener.open(embed_req, timeout=300.0) as response:
            result = json.loads(response.read().decode("utf-8"))
            question_embedding = result.get("embedding")
            if not question_embedding:
                raise Exception("Failed to generate embedding for question")
    except urllib.error.HTTPError as he:
        if he.code == 404:
            raise HTTPException(status_code=500, detail="Ollama 报错 404: 缺少向量模型。请在终端执行 'ollama pull nomic-embed-text'")
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(he)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")

    # 2. Hybrid Query: Vector Search + BM25
    chunks_text = []
    try:
        async def _query_db():
            conn = await asyncpg.connect(
                host="localhost",
                port=5433,
                database="aegis_assistant",
                user="aegis",
                password="aegis123"
            )
            try:
                # 获取所有 chunks 及其向量得分 (1 - 距离 = 相似度)
                # 可调参数: LIMIT 数量，如果库特别大，这里可以限制候选集大小
                rows = await conn.fetch(
                    """
                    SELECT id, chunk_text, 
                           1 - (embedding <=> $1::vector) AS vector_score
                    FROM kb_chunk
                    ORDER BY vector_score DESC
                    LIMIT 200
                    """,
                    str(question_embedding)
                )
                
                if not rows:
                    return []
                    
                chunks_map = {row['id']: row['chunk_text'] for row in rows}
                
                # 1. 向量检索排名
                vector_ranked_ids = [row['id'] for row in rows]
                
                # 2. 关键词 BM25 排名
                if jieba:
                    tokenized_corpus = [list(jieba.cut(row['chunk_text'])) for row in rows]
                    query_tokens = list(jieba.cut(request.question))
                else:
                    tokenized_corpus = [list(row['chunk_text']) for row in rows]
                    query_tokens = list(request.question)
                    
                bm25 = SimpleBM25(tokenized_corpus)
                bm25_scores = bm25.get_scores(query_tokens)
                
                # 按 BM25 分数排序
                bm25_ranked = sorted(zip([row['id'] for row in rows], bm25_scores), key=lambda x: x[1], reverse=True)
                bm25_ranked_ids = [item[0] for item in bm25_ranked]
                
                # 3. RRF 融合
                rrf_scores = compute_rrf(vector_ranked_ids, bm25_ranked_ids, k=60)
                
                # 按 RRF 分数排序
                fused_ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
                
                # 取 RRF 的 Top 10 进行精细重排序
                # 可调参数: top_k_fusion 提取进入重排的候选数量
                top_k_fusion = 10
                top_candidates = fused_ranked[:top_k_fusion]
                
                candidate_texts = [chunks_map[doc_id] for doc_id, _ in top_candidates]
                
                # 4. 使用 CrossEncoder 重排序 (已注释)
                if reranker and candidate_texts:
                    pairs = [[request.question, text] for text in candidate_texts]
                    scores = reranker.predict(pairs)
                    
                    # 按重排分数排序
                    reranked = sorted(zip(candidate_texts, scores), key=lambda x: x[1], reverse=True)
                    # 可调参数: top_k_final 最终喂给 LLM 的 chunk 数量
                    top_k_final = 3
                    return [text for text, score in reranked[:top_k_final]]
                else:
                    # 如果没有安装 sentence-transformers，则直接使用 RRF 的 Top 3
                    top_k_final = 3
                    return candidate_texts[:top_k_final]

                # 暂时跳过精细重排，直接使用混合检索 (RRF) 融合后的 Top 3
                top_k_final = 3
                return candidate_texts[:top_k_final]
                    
            finally:
                await conn.close()

        chunks_text = asyncio.run(_query_db())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hybrid search failed: {str(e)}")

    # 3. Construct RAG prompt
    context = "\n\n".join(chunks_text)
    prompt = f"Context: {context}\nQuestion: {request.question}"

    # 4. Send the new prompt to qwen:1.8b
    ollama_url = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": "qwen:1.8b",
        "prompt": prompt,
        "stream": False,
        "keep_alive": "10m"
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ollama_url,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    last_error = "未知错误"
    for attempt in range(3):
        try:
            with opener.open(req, timeout=300.0) as response:
                result = json.loads(response.read().decode("utf-8"))
                answer = result.get("response", "").strip()
                if not answer:
                    raise HTTPException(status_code=502, detail="Ollama 返回空响应")
                return {"answer": answer}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="ignore")
            last_error = f"HTTP {e.code}: {error_body or e.reason}"
        except Exception as e:
            last_error = str(e)

        if attempt < 2:
            time.sleep(1)

    raise HTTPException(status_code=500, detail=f"Ollama request failed after retries: {last_error}")
