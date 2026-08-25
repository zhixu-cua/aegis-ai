import asyncio
import json
import os
import redis.asyncio as redis
from api.services.ingestion.listener import start_listener, stop_listener

observers = {}

async def listen_commands(pg_pool=None):
    redis_url = os.getenv("REDIS_URL", "redis://:aegis123@localhost:6379/0")
    # 为了兼容 Redis 5.0，我们显式指定协议和连接参数
    r = redis.Redis(host='localhost', port=6379, db=0, password='aegis123', decode_responses=True, health_check_interval=30, protocol=2)
    
    stream_key = "listener_command"
    group_name = "command_workers"
    consumer_name = "worker_1"
    
    try:
        await r.xgroup_create(stream_key, group_name, id="0", mkstream=True)
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            print(f"Failed to create group for command stream: {e}")

    # 服务重启后，重建所有“启用中 + 实时同步”的数据源的文件监听器，
    # 避免重启导致 watchdog 丢失、自动同步失效（只能手动强制刷新才能同步）
    if pg_pool is not None:
        try:
            await _recover_realtime_listeners(r, pg_pool)
        except Exception as e:
            print(f"Recover realtime listeners failed: {e}")

    print("Command listener started...")
    while True:
        try:
            results = await r.xreadgroup(
                groupname=group_name,
                consumername=consumer_name,
                streams={stream_key: ">"},
                count=1,
                block=5000
            )
            for stream, messages in results:
                for msg_id, data in messages:
                    try:
                        if 'data' in data:
                            cmd = json.loads(data['data'])
                            action = cmd.get('action')
                            ds_id = cmd.get('datasource_id')
                            if action == 'start':
                                path = cmd.get('path')
                                if not path or not os.path.exists(path):
                                    print(f"Invalid or empty path for datasource {ds_id}: '{path}'")
                                elif ds_id not in observers:
                                    print(f"Starting listener for {ds_id} on {path}")
                                    observer = start_listener(ds_id, path, redis_url)
                                    observers[ds_id] = observer
                                    # 触发初始同步，将目录路径作为一个 modified 事件发入队列，由 worker 遍历
                                    normalized_path = path.replace('\\', '/')
                                    import time
                                    event_data = {
                                        "datasource_id": str(ds_id),
                                        "event_type": "modified",
                                        "file_path": normalized_path,
                                        "timestamp": time.time()
                                    }
                                    await r.xadd("doc_events", event_data, maxlen=10000)
                            elif action == 'stop':
                                if ds_id in observers:
                                    print(f"Stopping listener for {ds_id}")
                                    stop_listener(observers[ds_id])
                                    del observers[ds_id]
                    except Exception as e:
                        print(f"Error processing command {data}: {e}")
                    await r.xack(stream_key, group_name, msg_id)
        except asyncio.CancelledError:
            break
        except Exception as e:
            if "Timeout" not in str(e):
                print(f"Command listener error: {e}")
            await asyncio.sleep(5)


async def _recover_realtime_listeners(r: redis.Redis, pg_pool):
    """
    服务重启后恢复所有「启用中 + 实时同步」数据源的文件监听器。
    通过向 listener_command 流重新下发 start 命令，复用主循环中的监听启动逻辑。
    """
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, source_type, source_config FROM kb_datasource "
            "WHERE status = 'active' AND sync_frequency = 'realtime'"
        )
        for row in rows:
            ds_id = row['id']
            source_type = row['source_type']
            sc = row['source_config']
            if isinstance(sc, str):
                sc = json.loads(sc)
            path = ""
            if isinstance(sc, dict):
                if source_type == 'cos':
                    path = str(sc.get('prefix') or '')
                else:
                    path = str(sc.get('path') or '')
            if not path:
                print(f"Skip recovering listener for datasource {ds_id}: empty path")
                continue
            cmd = {"action": "start", "datasource_id": ds_id, "path": path}
            await r.xadd("listener_command", {"data": json.dumps(cmd)}, maxlen=10000)
            print(f"Recovered realtime listener: datasource_id={ds_id}, path={path}")