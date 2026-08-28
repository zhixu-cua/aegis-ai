"""
共享数据库连接池引用。

main.py 在启动时通过 set_pool() 注入连接池；
chat.py / kb.py 等通过 get_pool() 复用，避免每次请求都新建连接。
"""

import asyncpg

_pool: asyncpg.Pool = None


def set_pool(pool: asyncpg.Pool):
    global _pool
    _pool = pool


def get_pool() -> asyncpg.Pool:
    return _pool
