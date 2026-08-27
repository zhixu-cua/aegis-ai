"""
文档处理 Worker 模块
从 Redis Stream 消费事件，执行文档的解析、切片、向量化和入库
"""

import asyncio
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

import asyncpg
import redis.asyncio as redis
import httpx


class DocumentWorker:
    """文档处理 Worker"""
    
    def __init__(
        self,
        pg_pool: asyncpg.Pool,
        redis_client: redis.Redis,
        backend_url: str = "http://backend:8082"
    ):
        self.pg_pool = pg_pool
        self.redis = redis_client
        self.backend_url = backend_url
        self.stream_key = "doc_events"
        self.group_name = "doc_workers"
        # 使用固定的消费者名，避免每次重启都产生新的消费者，导致消费组中堆积大量已死消费者
        self.consumer_name = "worker_1"
        self.running = False
        # 限制最大并发处理文件数为 3，防止大文件夹同步时 OOM (内存溢出)
        self.semaphore = asyncio.Semaphore(3)
        
    async def start(self):
        """启动 Worker 消费循环"""
        # 创建消费组（如果不存在）
        try:
            await self.redis.xgroup_create(
                self.stream_key, self.group_name, id="0", mkstream=True
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
        
        # 启动时回收历史遗留的 pending 消息（被已退出消费者占用），避免重启导致消息卡死、文件无法重新同步
        await self._recover_pending()
        
        self.running = True
        while self.running:
            try:
                results = await self.redis.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={self.stream_key: ">"},
                    count=1,
                    block=5000
                )
                
                for stream, messages in results:
                    for msg_id, data in messages:
                        ok = await self._process_with_retry(data)
                        await self.redis.xack(self.stream_key, self.group_name, msg_id)
                        if not ok:
                            # 重试耗尽：写入死信流，便于人工排查与重放
                            try:
                                await self.redis.xadd("doc_events_dead", data, maxlen=10000)
                            except Exception as e:
                                print(f"发布死信失败: {e}")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                # 忽略正常的 Timeout 错误
                if "Timeout" not in str(e.__class__.__name__) and "Timeout" not in str(e):
                    print(f"Worker error: {e}")
                await asyncio.sleep(1)
    
    async def stop(self):
        """停止 Worker"""
        self.running = False

    async def _recover_pending(self):
        """
        服务重启后，回收历史遗留的 pending 消息并重新处理：
        1) 用 XAUTOCLAIM 把 idle 超过 60 秒的 pending 消息从旧消费者认领到当前消费者；
        2) 读取并处理当前消费者名下所有 pending 消息。
        处理逻辑本身幂等（按 file_hash 去重），重复处理不会产生脏数据。
        """
        try:
            await self.redis.xautoclaim(
                self.stream_key, self.group_name, self.consumer_name,
                min_idle_time=60000, start_id="0", count=100
            )
        except Exception as e:
            print(f"XAUTOCLAIM failed: {e}")
            return

        try:
            while True:
                result = await self.redis.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={self.stream_key: "0"},
                    count=10,
                    block=100
                )
                if not result:
                    break
                got_any = False
                for stream, messages in result:
                    for msg_id, data in messages:
                        got_any = True
                        try:
                            await self._process_event(data)
                        except Exception as e:
                            print(f"Recover pending event error: {e}")
                        await self.redis.xack(self.stream_key, self.group_name, msg_id)
                if not got_any:
                    break
        except Exception as e:
            print(f"Recover pending read failed: {e}")

    async def _process_with_retry(self, event: Dict[bytes, bytes], max_attempt: int = 3) -> bool:
        """处理单条事件，失败自动重试（指数退避）；最终失败记录死信到 ingest_task。"""
        ds_id, fpath = self._parse_event_meta(event)
        last_error = ""
        for attempt in range(1, max_attempt + 1):
            try:
                await self._process_event(event)
                return True
            except asyncio.CancelledError:
                raise
            except Exception as e:
                last_error = str(e)
                print(f"处理事件失败 (attempt {attempt}/{max_attempt}) ds={ds_id} path={fpath}: {last_error}")
                if attempt < max_attempt:
                    await asyncio.sleep(2 ** attempt)
        # 死信记录
        try:
            async with self.pg_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO ingest_task (datasource_id, file_path, status, attempt, max_attempt, error_msg)
                    VALUES ($1, $2, 'dead', $3, $4, $5)
                """, ds_id, fpath or '', max_attempt, max_attempt, last_error[:500])
        except Exception as e:
            print(f"记录死信失败: {e}")
        return False

    def _parse_event_meta(self, event: Dict[bytes, bytes]):
        """从事件中提取 datasource_id 与 file_path（用于死信记录，尽力而为）。"""
        ds_id = None
        fpath = ''
        try:
            if b'data' in event:
                import json
                d = json.loads(event[b'data'].decode())
                ds_id = int(d.get('datasource_id', 0)) or None
                fpath = d.get('file_path', '')
            else:
                ds_id = int(event.get(b'datasource_id', b'0')) or None
                fpath = event.get(b'file_path', b'').decode()
        except Exception:
            pass
        return ds_id, fpath

    async def _process_event(self, event: Dict[bytes, bytes]):
        """处理单个文档事件"""
        # 兼容 Java 发送的 JSON 字符串包裹在 'data' 字段中的情况
        if b'data' in event:
            import json
            try:
                data_dict = json.loads(event[b'data'].decode())
                event_type = data_dict.get('event_type', '')
                file_path = data_dict.get('file_path', '')
                datasource_id = int(data_dict.get('datasource_id', 0))
            except Exception as e:
                print(f"Failed to parse JSON data from event: {e}")
                return
        else:
            event_type = event.get(b'event_type', b'').decode()
            file_path = event.get(b'file_path', b'').decode()
            datasource_id = int(event.get(b'datasource_id', b'0'))

        if not file_path or not datasource_id:
            return

        # 查询数据源类型和配置
        source_type = 'local'
        source_config = {}
        try:
            async with self.pg_pool.acquire() as conn:
                ds = await conn.fetchrow(
                    "SELECT source_type, source_config FROM kb_datasource WHERE id = $1",
                    datasource_id
                )
                if ds:
                    source_type = ds['source_type']
                    # source_config 可能是 JSON 字符串或 dict
                    sc = ds['source_config']
                    if isinstance(sc, str):
                        import json
                        source_config = json.loads(sc)
                    elif isinstance(sc, dict):
                        source_config = sc
        except Exception as e:
            print(f"查询数据源失败: {e}")

        if source_type == 'cos':
            await self._process_cos_event(datasource_id, source_config, event_type, file_path)
            return

        # 如果路径是文件夹，则遍历该文件夹下的所有文件进行处理（支持初始同步或强制刷新文件夹）
        if os.path.isdir(file_path):
            if event_type == "deleted":
                # 暂时不支持直接删除整个文件夹的逻辑，或者可以遍历查询数据库删除
                return
                
            # 支持的文件格式列表
            SUPPORTED_EXTS = {'.txt', '.md', '.pdf', '.docx', '.doc', '.xlsx', '.xls', '.csv', '.png', '.jpg', '.jpeg', '.html', '.htm'}
            
            print(f"检测到文件夹同步请求，开始遍历目录: {file_path}")
            for root, dirs, files in os.walk(file_path):
                # 忽略隐藏目录
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in files:
                    # 忽略隐藏文件或临时文件
                    if f.startswith('.') or f.startswith('~'):
                        continue
                        
                    # 校验文件格式
                    ext = os.path.splitext(f)[1].lower()
                    if ext not in SUPPORTED_EXTS:
                        continue
                        
                    full_path = os.path.join(root, f)
                    # 递归调用自身处理单文件，避免阻塞当前主逻辑太久
                    # 注意：这里我们使用 asyncio.create_task 后台执行，避免单次循环过长
                    asyncio.create_task(self._handle_upsert(datasource_id, full_path, full_path))
            return

        # 检查文件是否存在（删除事件除外）
        if event_type != "deleted" and not os.path.exists(file_path):
            await self._notify_progress(datasource_id, file_path, "failed", 
                                         error="文件不存在")
            return
            
        # 校验单文件格式是否支持
        SUPPORTED_EXTS = {'.txt', '.md', '.pdf', '.docx', '.doc', '.xlsx', '.xls', '.csv', '.png', '.jpg', '.jpeg', '.html', '.htm'}
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in SUPPORTED_EXTS:
            return
        
        if event_type == "deleted":
            await self._handle_delete(datasource_id, file_path)
        elif event_type in ("created", "modified"):
            await self._handle_upsert(datasource_id, file_path, file_path)

    async def _process_cos_event(self, datasource_id: int, source_config: dict, event_type: str, file_path: str):
        """处理 COS 数据源的事件"""
        if event_type == "deleted":
            await self._handle_delete(datasource_id, file_path)
            return
            
        secret_id = source_config.get('secretId')
        secret_key = source_config.get('secretKey')
        region = source_config.get('region')
        bucket = source_config.get('bucket')
        prefix = source_config.get('prefix', '')
        
        if not all([secret_id, secret_key, region, bucket]):
            print(f"COS config incomplete for datasource {datasource_id}")
            return
            
        from .cos import COSConnector
        connector = COSConnector(secret_id, secret_key, region)
        
        # 确定需要同步的前缀
        sync_prefix = file_path if file_path and file_path != '/' else prefix
        
        print(f"检测到 COS 同步请求，开始拉取: bucket={bucket}, prefix={sync_prefix}")
        
        try:
            # list_files 会返回匹配前缀的所有文件
            files = await asyncio.to_thread(connector.list_files, bucket, sync_prefix)
            if not files:
                # 尝试作为单文件获取
                file_info = await asyncio.to_thread(connector.get_file_info, bucket, sync_prefix)
                if file_info:
                    files = [file_info]
                else:
                    print(f"COS 找不到匹配的文件: bucket={bucket}, prefix={sync_prefix}")
                    await self._notify_progress(datasource_id, sync_prefix, "failed", error="COS 中未找到该文件")
                    return

            SUPPORTED_EXTS = {'.txt', '.md', '.pdf', '.docx', '.doc', '.xlsx', '.xls', '.csv', '.png', '.jpg', '.jpeg', '.html', '.htm'}
            for file_info in files:
                key = file_info['key']
                etag = file_info['etag']
                
                # 校验 COS 文件格式
                ext = os.path.splitext(key)[1].lower()
                if ext not in SUPPORTED_EXTS:
                    continue
                
                # 直接将 COS 的 key 作为逻辑路径
                logical_key = key
                
                # 将该文件的处理加入异步任务，避免阻塞主循环
                asyncio.create_task(
                    self._handle_cos_upsert(connector, bucket, key, etag, datasource_id, logical_key)
                )
        except Exception as e:
            print(f"COS 同步失败: {e}")
            await self._notify_progress(datasource_id, file_path, "failed", error=str(e))

    async def _handle_cos_upsert(self, connector, bucket: str, key: str, etag: str, datasource_id: int, logical_key: str):
        """处理 COS 单文件的智能同步（基于 ETag 去重，使用阅后即焚的临时文件）"""
        async with self.semaphore:
            try:
                # 1. 检查数据库是否存在且未修改
                async with self.pg_pool.acquire() as conn:
                    # 查询同路径的所有文档记录
                    existing_docs = await conn.fetch(
                        "SELECT id, file_hash, status FROM kb_document WHERE datasource_id=$1 AND file_path=$2",
                        datasource_id, logical_key
                    )
                    
                    already_synced = False
                    for doc in existing_docs:
                        if doc['file_hash'] == etag and doc['status'] != 'failed':
                            already_synced = True
                            break
                            
                    if already_synced:
                        print(f"COS 文件未变化，跳过同步: {logical_key}")
                        # 顺手清理因过去哈希算法改变产生的同路径旧数据，防止出现重复
                        for doc in existing_docs:
                            if doc['file_hash'] != etag:
                                await conn.execute("DELETE FROM kb_chunk WHERE document_id = $1", doc['id'])
                                await conn.execute("DELETE FROM kb_document WHERE id = $1", doc['id'])
                        return
                    
                    # 如果需要重新同步，先删除旧版本数据，避免产生相同 file_path 的多条记录
                    for doc in existing_docs:
                        await conn.execute("DELETE FROM kb_chunk WHERE document_id = $1", doc['id'])
                        await conn.execute("DELETE FROM kb_document WHERE id = $1", doc['id'])
                
                # 2. 如果不存在或已修改，则下载到阅后即焚的临时文件中
                import tempfile
                import os
                
                # 获取文件扩展名，以便解析器识别
                ext = os.path.splitext(key)[1]
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
                    temp_path = temp_file.name
                
                try:
                    # 下载文件内容到临时路径（异步执行，避免阻塞主线程）
                    success = await asyncio.to_thread(connector.download_file, bucket, key, temp_path)
                    if not success:
                        await self._notify_progress(datasource_id, logical_key, "failed", error="COS 文件下载到内存/临时文件失败")
                        return
                    
                    # 复用原有的处理逻辑（解析 -> 切片 -> 向量化 -> 入库），此时 hash 直接使用 ETag
                    # 注意：我们这里不需要再调 _handle_upsert，因为那会重复查库和算 hash
                    
                    # 3. 解析文档
                    from .parser import parse_document
                    content = await asyncio.to_thread(parse_document, temp_path)
                    if not content or len(content.strip()) < 10:
                        await self._notify_progress(datasource_id, logical_key, "failed", error="文档内容为空或解析失败")
                        return
                    
                    # 3.5 数据清洗
                    from .cleaner import clean_text
                    content = await asyncio.to_thread(clean_text, content)
                    if not content or len(content.strip()) < 10:
                        await self._notify_progress(datasource_id, logical_key, "failed", error="文档清洗后内容过少")
                        return
                    
                    # 4. 切片
                    from .chunker import chunk_text
                    chunks = await asyncio.to_thread(chunk_text, content)
                    if not chunks:
                        await self._notify_progress(datasource_id, logical_key, "failed", error="切片结果为空")
                        return
                    
                    # 5. 生成向量并入库
                    from .vector_store import upsert_chunks
                    doc_id = await upsert_chunks(
                        pool=self.pg_pool,
                        datasource_id=datasource_id,
                        file_path=logical_key,
                        file_hash=etag,  # 直接使用 COS ETag 作为哈希
                        blocks=chunks
                    )
                    
                    # 6. 更新文档状态
                    async with self.pg_pool.acquire() as conn:
                        await conn.execute("""
                            UPDATE kb_document 
                            SET status = 'completed', chunk_count = $1, processed_at = NOW(), error_message = NULL
                            WHERE id = $2
                        """, len(chunks), doc_id)
                    
                    # 7. 推送成功状态
                    await self._notify_progress(datasource_id, logical_key, "completed", chunk_count=len(chunks))
                    
                finally:
                    # 无论成功失败，确保删除临时文件，释放磁盘空间
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except Exception as e:
                            print(f"清理临时文件失败 {temp_path}: {e}")
                            
            except Exception as e:
                error_msg = str(e)
                print(f"处理 COS 文档失败 {logical_key}: {error_msg}")
                await self._notify_progress(datasource_id, logical_key, "failed", error=error_msg)
                async with self.pg_pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE kb_document SET status = 'failed', error_message = $1, updated_at = NOW()
                        WHERE datasource_id = $2 AND file_path = $3
                    """, error_msg[:500], datasource_id, logical_key)
                raise

    async def _handle_upsert(self, datasource_id: int, logical_path: str, physical_path: str):
        """处理新增/修改：解析 -> 切片 -> 向量化 -> 入库"""
        async with self.semaphore:
            try:
                # 1. 计算文件哈希
                file_hash = await asyncio.to_thread(self._calc_hash, physical_path)
                
                # 2. 检查是否已处理（去重及清理旧版本）
                async with self.pg_pool.acquire() as conn:
                    existing_docs = await conn.fetch(
                        "SELECT id, file_hash, status FROM kb_document WHERE datasource_id=$1 AND file_path=$2",
                        datasource_id, logical_path
                    )
                    
                    already_synced = False
                    for doc in existing_docs:
                        if doc['file_hash'] == file_hash and doc['status'] != 'failed':
                            already_synced = True
                            break
                            
                    if already_synced:
                        print(f"文件未变化，跳过: {logical_path}")
                        # 清理同路径旧哈希的垃圾数据
                        for doc in existing_docs:
                            if doc['file_hash'] != file_hash:
                                await conn.execute("DELETE FROM kb_chunk WHERE document_id = $1", doc['id'])
                                await conn.execute("DELETE FROM kb_document WHERE id = $1", doc['id'])
                        return
                        
                    # 如果有修改，删除旧版本，避免产生重复记录
                    for doc in existing_docs:
                        await conn.execute("DELETE FROM kb_chunk WHERE document_id = $1", doc['id'])
                        await conn.execute("DELETE FROM kb_document WHERE id = $1", doc['id'])
                
                # 3. 解析文档
                from .parser import parse_document
                content = await asyncio.to_thread(parse_document, physical_path)
                if not content or len(content.strip()) < 10:
                    await self._notify_progress(datasource_id, logical_path, "failed", 
                                                 error="文档内容为空或解析失败")
                    return
                
                # 3.5 数据清洗
                from .cleaner import clean_text
                content = await asyncio.to_thread(clean_text, content)
                if not content or len(content.strip()) < 10:
                    await self._notify_progress(datasource_id, logical_path, "failed", 
                                                 error="文档清洗后内容过少")
                    return
                
                # 4. 切片
                from .chunker import chunk_text
                chunks = await asyncio.to_thread(chunk_text, content)
                if not chunks:
                    await self._notify_progress(datasource_id, logical_path, "failed", 
                                                 error="切片结果为空")
                    return
                
                # 5. 生成向量并入库
                from .vector_store import upsert_chunks
                doc_id = await upsert_chunks(
                    pool=self.pg_pool,
                    datasource_id=datasource_id,
                    file_path=logical_path,
                    file_hash=file_hash,
                    blocks=chunks
                )
                
                # 6. 更新文档状态
                async with self.pg_pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE kb_document 
                        SET status = 'completed', chunk_count = $1, processed_at = NOW(), error_message = NULL
                        WHERE id = $2
                    """, len(chunks), doc_id)
                
                # 7. 推送成功状态
                await self._notify_progress(datasource_id, logical_path, "completed", 
                                             chunk_count=len(chunks))
                
            except Exception as e:
                error_msg = str(e)
                print(f"处理文档失败 {logical_path}: {error_msg}")
                await self._notify_progress(datasource_id, logical_path, "failed", error=error_msg)
                # 更新数据库错误状态
                async with self.pg_pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE kb_document SET status = 'failed', error_message = $1, updated_at = NOW()
                        WHERE datasource_id = $2 AND file_hash = $3
                    """, error_msg[:500], datasource_id, file_hash)
                raise
    
    async def _handle_delete(self, datasource_id: int, file_path: str):
        """删除：删除向量块和文档记录 (物理删除)"""
        try:
            async with self.pg_pool.acquire() as conn:
                # 查询文档 ID
                doc = await conn.fetchrow(
                    "SELECT id FROM kb_document WHERE datasource_id=$1 AND file_path=$2",
                    datasource_id, file_path
                )
                if not doc:
                    return
                
                doc_id = doc['id']
                
                # 删除向量块
                await conn.execute("""
                    DELETE FROM kb_chunk WHERE document_id = $1
                """, doc_id)
                
                # 物理删除文档状态
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
            
            # 推送删除状态
            await self._notify_progress(datasource_id, file_path, "deleted")
            
        except Exception as e:
            print(f"删除文档失败 {file_path}: {e}")
    
    def _calc_hash(self, file_path: str) -> str:
        """计算文件 SHA256"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    async def _notify_progress(self, datasource_id: int, file_path: str, status: str, **kwargs):
        """通过 WebSocket 推送状态更新"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                payload = {
                    "datasource_id": datasource_id,
                    "file_path": file_path,
                    "status": status,
                    **kwargs
                }
                await client.post(
                    f"{self.backend_url}/api/internal/ws/progress",
                    json=payload
                )
        except Exception as e:
            print(f"推送状态失败: {e}")


async def create_worker(
    pg_pool: asyncpg.Pool,
    redis_url: str,
    backend_url: str = "http://backend:8082"
) -> DocumentWorker:
    """创建 Worker 实例"""
    redis_client = redis.Redis(host='localhost', port=6379, db=0, password='aegis123', decode_responses=False, protocol=2)
    return DocumentWorker(pg_pool, redis_client, backend_url)
