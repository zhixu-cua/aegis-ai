"""
结构化日志工具：统一输出格式 + request_id 贯穿（P0 可观测性）。

用法：
    from api.logging_utils import get_logger, set_request_id
    set_request_id(uuid4().hex[:12])   # 每个请求/任务开始时设置
    log = get_logger("rag")
    log.info("...")
"""

import contextvars
import logging
import sys
import time

_request_id_var = contextvars.ContextVar("request_id", default="-")


def set_request_id(rid: str):
    _request_id_var.set(rid)


def get_request_id() -> str:
    return _request_id_var.get()


class StructuredFormatter(logging.Formatter):
    """输出格式：时间 级别 [req=xxx] logger: 消息"""

    def format(self, record):
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created))
        rid = get_request_id()
        return f"{ts} {record.levelname} [req={rid}] {record.name}: {record.getMessage()}"


def setup_logging(level: int = logging.INFO):
    root = logging.getLogger()
    root.setLevel(level)
    # 清空已有 handler，避免重复输出
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
