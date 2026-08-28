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
    async with pool.acquire() as conn:
        # 开启事务
        async with conn.transaction():
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
            client = ollama.AsyncClient(host="http://127.0.0.1:11434")
            for idx, (chunk_text, metadata) in enumerate(chunks):
                try:
                    embedding_response = await client.embeddings(
                        model="bge-m3",
                        prompt=chunk_text
                    )
                    embedding = embedding_response["embedding"]
                except Exception as e:
                    # 抛出异常，触发事务回滚
                    raise RuntimeError(f"生成向量失败 (chunk {idx}): {e}") from e

                await conn.execute("""
                    INSERT INTO kb_chunk (
                        document_id, chunk_text, embedding, chunk_index
                    ) VALUES ($1, $2, $3, $4)
                """, doc_id, chunk_text, str(embedding), idx)

                # 可保留 sleep，但注意事务内 sleep 会占用连接，建议去掉或缩小
                # await asyncio.sleep(0.01)

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
