"""
向量存储封装模块
封装 pgvector 的 CRUD 操作
"""

import asyncio
from typing import List, Tuple, Optional

import asyncpg
import ollama


async def upsert_chunks(
    pool: asyncpg.Pool,
    datasource_id: int,
    file_path: str,
    file_hash: str,
    chunks: List[Tuple[str, dict]]
) -> int:
    """
    将切块向量化后存入 pgvector
    
    Args:
        pool: PostgreSQL 连接池
        datasource_id: 数据源 ID
        file_path: 文件路径
        file_hash: 文件哈希
        chunks: 切块列表 [(text, metadata), ...]
    
    Returns:
        int: 文档记录 ID
    """
    async with pool.acquire() as conn:
        # 1. 插入或更新文档记录
        doc_id = await conn.fetchval("""
            INSERT INTO kb_document (datasource_id, file_path, file_hash, status, chunk_count)
            VALUES ($1, $2, $3, 'processing', 0)
            ON CONFLICT (datasource_id, file_hash) DO UPDATE 
            SET status = 'processing', updated_at = NOW(), error_message = NULL
            RETURNING id
        """, datasource_id, file_path, file_hash)
        
        # 2. 删除旧的向量块
        await conn.execute("""
            DELETE FROM kb_chunk WHERE document_id = $1
        """, doc_id)
        
        # 3. 批量生成向量并插入
        # 显式指定 host 为 127.0.0.1，防止系统环境变量 OLLAMA_HOST=0.0.0.0 导致 httpx 解析错误
        client = ollama.AsyncClient(host="http://127.0.0.1:11434")
        for idx, (chunk_text, metadata) in enumerate(chunks):
            # 调用 Ollama 生成向量（使用异步客户端避免阻塞事件循环）
            try:
                embedding_response = await client.embeddings(
                    model="nomic-embed-text",
                    prompt=chunk_text
                )
                embedding = embedding_response["embedding"]
            except Exception as e:
                print(f"生成向量失败: {e}")
                continue

            # 插入新向量块
            # pgvector 要求将 Python 的 list 转换为字符串格式，例如 '[1.1, 2.2, 3.3]' 才能插入到 vector 类型的列中
            await conn.execute("""
                INSERT INTO kb_chunk (
                    document_id, chunk_text, embedding, chunk_index
                ) VALUES ($1, $2, $3, $4)
            """, doc_id, chunk_text, str(embedding), idx)
            
            # 释放控制权，防止 CPU 被长时间独占导致系统卡死
            await asyncio.sleep(0.05)
        
        # 4. 更新文档状态
        await conn.execute("""
            UPDATE kb_document 
            SET status = 'completed', chunk_count = $1, processed_at = NOW()
            WHERE id = $2
        """, len(chunks), doc_id)
        
        # 5. 更新数据源的文档计数
        await conn.execute("""
            UPDATE kb_datasource 
            SET total_doc_count = (
                SELECT COUNT(*) FROM kb_document 
                WHERE datasource_id = $1 AND status = 'completed'
            ), last_sync_at = NOW()
            WHERE id = $1
        """, datasource_id)
        
        return doc_id


async def delete_chunks_by_document(
    pool: asyncpg.Pool,
    datasource_id: int,
    file_path: str
) -> bool:
    """删除指定文档的所有向量块"""
    async with pool.acquire() as conn:
        # 查询文档 ID
        doc = await conn.fetchrow(
            "SELECT id FROM kb_document WHERE datasource_id=$1 AND file_path=$2",
            datasource_id, file_path
        )
        if not doc:
            return False
        
        doc_id = doc['id']
        
        # 删除向量块
        await conn.execute("""
            DELETE FROM kb_chunk WHERE document_id = $1
        """, doc_id)
        
        # 物理删除文档记录
        await conn.execute("""
            DELETE FROM kb_document WHERE id = $1
        """, doc_id)
        
        # 更新数据源计数
        await conn.execute("""
            UPDATE kb_datasource 
            SET total_doc_count = (
                SELECT COUNT(*) FROM kb_document 
                WHERE datasource_id = $1 AND status = 'completed'
            ), last_sync_at = NOW()
            WHERE id = $1
        """, datasource_id)
        
        return True
