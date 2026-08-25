"""
文件监听器模块
使用 watchdog 监控指定文件夹，将文件变化事件发送到 Redis Stream
"""

import asyncio
import json
import threading
from pathlib import Path
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import redis.asyncio as redis


class DocumentHandler(FileSystemEventHandler):
    """监控本地文件夹变化，发送事件到 Redis Stream"""
    
    def __init__(self, datasource_id: int, redis_client: redis.Redis):
        self.datasource_id = datasource_id
        self.redis = redis_client
        self.stream_key = "doc_events"
        
        # 忽略的文件扩展名
        self.ignore_extensions = {'.tmp', '.swp', '.~', '.DS_Store', '.gitkeep'}
        
    def on_created(self, event):
        if not event.is_directory and not self._should_ignore(event.src_path):
            self._publish_event("created", event.src_path)
            
    def on_modified(self, event):
        if not event.is_directory and not self._should_ignore(event.src_path):
            self._publish_event("modified", event.src_path)
            
    def on_deleted(self, event):
        if not event.is_directory and not self._should_ignore(event.src_path):
            self._publish_event("deleted", event.src_path)
    
    def _should_ignore(self, path: str) -> bool:
        """判断是否应忽略该文件"""
        ext = Path(path).suffix.lower()
        return ext in self.ignore_extensions
    
    def _publish_event(self, event_type: str, path: str):
        """发布事件到 Redis Stream"""
        # 兼容 Windows 路径：将反斜杠替换为正斜杠，防止被 JSON 或者 Redis 客户端截断
        normalized_path = path.replace('\\', '/')
        import time
        event_data = {
            "datasource_id": str(self.datasource_id),
            "event_type": event_type,
            "file_path": normalized_path,
            "timestamp": time.time()
        }
        try:
            # self.redis 已经是同步客户端，且 redis-py 的连接池是线程安全的，可以直接使用
            self.redis.xadd(self.stream_key, event_data, maxlen=10000)
        except Exception as e:
            print(f"Failed to publish event: {e}")


def start_listener(datasource_id: int, path: str, redis_url: str) -> Observer:
    """
    启动文件监听器
    
    Args:
        datasource_id: 数据源 ID
        path: 要监控的文件夹路径
        redis_url: Redis 连接字符串
    
    Returns:
        Observer: watchdog Observer 实例
    """
    import redis as sync_redis
    redis_client = sync_redis.Redis(host='localhost', port=6379, db=0, password='aegis123', protocol=2)
    handler = DocumentHandler(datasource_id, redis_client)
    observer = Observer()
    observer.schedule(handler, path, recursive=True)
    observer.start()
    return observer


def stop_listener(observer: Observer):
    """停止文件监听器"""
    if observer:
        observer.stop()
        observer.join()