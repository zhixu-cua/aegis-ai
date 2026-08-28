"""
共享中文分词模块。

入库（写入倒排索引）与检索（查询切词）必须使用同一套分词逻辑，
否则 BM25 关键词命中率会不一致。此处统一提供 tokenize()。

优先使用 jieba（精确中文分词）；未安装时退回「字符 + 二元词组」，
避免退化成纯单字匹配。
"""

import re

try:
    import jieba
    try:
        jieba.initialize()
    except Exception:
        pass
except ImportError:
    jieba = None


def tokenize(text: str):
    """对文本分词，返回 token 列表。"""
    if not text:
        return []
    if jieba is not None:
        return [t for t in jieba.cut(text) if t.strip()]

    tokens = []
    tokens.extend(re.findall(r"[a-zA-Z0-9_]+", text))
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        tokens.extend(run)  # 单字
        tokens.extend(run[i:i + 2] for i in range(len(run) - 1))  # 二元组
    return tokens
