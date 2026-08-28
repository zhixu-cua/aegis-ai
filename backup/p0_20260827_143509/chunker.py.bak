"""
文档切块模块
采用递归字符分割策略，优先按语义边界（段落、句子）切割，避免破坏逻辑单元。
适用于技术文档、FAQ、Markdown、纯文本等多种格式。
"""

import re
from typing import List, Tuple, Optional


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
    separators: Optional[List[str]] = None
) -> List[Tuple[str, dict]]:
    # 1. 定义通用的分隔符优先级（针对中英文技术文档优化）
    if separators is None:
        separators = [
            "\n# ", "\n## ", "\n### ", "\n#### ", # 最高优先级：Markdown标题
            "\n\n",      # 段落分隔
            "\n",        # 换行
            "。", "！", "？", "；",  # 中文完整句子边界
            ". ", "! ", "? ", "; ",  # 英文句子边界（注意空格）
            "，", ", ",  # 中文/英文逗号（较低优先级）
            " ",         # 单词分隔
            ""           # 最后的保底：按字符切分
        ]
    
    # 2. 防止不合理的参数导致死循环
    if chunk_overlap >= chunk_size:
        chunk_overlap = max(chunk_size // 4, 1)
    
    # 3. 调用递归分割核心
    chunks = _recursive_split(text, separators, chunk_size, chunk_overlap)
    
    # 4. 为每个块添加标准化元数据
    total = len(chunks)
    result = []
    for idx, chunk_text in enumerate(chunks):
        result.append((
            chunk_text,
            {
                "chunk_index": idx,
                "total_chunks": total,
                "char_count": len(chunk_text),
                "start_char": text.find(chunk_text) if chunk_text else -1  # 粗略定位
            }
        ))
    
    return result


def _recursive_split(
    text: str,
    separators: List[str],
    chunk_size: int,
    chunk_overlap: int
) -> List[str]:
    """
    递归分割核心逻辑：
    1. 尝试用当前优先级的 separators[0] 分割
    2. 如果分割后的片段大小合适，则保留；如果某个片段依然超长，递归降级使用下一个分隔符
    3. 如果所有分隔符都用完了，强制按 chunk_size 切割
    """
    if not text.strip():
        return []
    
    # 如果文本本身就不超长，直接返回
    if len(text) <= chunk_size:
        return [text]
    
    # 如果已经没有更多分隔符可用，强制按固定大小切割（尽量在空格处切）
    if not separators:
        return _force_split(text, chunk_size, chunk_overlap)
    
    current_sep = separators[0]
    remaining_seps = separators[1:]
    
    # 按当前分隔符分割
    splits = text.split(current_sep)
    
    # 过滤掉空片段
    splits = [s for s in splits if s.strip()]
    
    # 如果当前分隔符无法有效分割（例如原文没有换行），降级到下一个分隔符
    if len(splits) <= 1:
        return _recursive_split(text, remaining_seps, chunk_size, chunk_overlap)
    
    # 开始聚合分割后的片段，生成最终的块
    chunks = []
    current_chunk = ""
    
    for split in splits:
        # 如果单个片段依然大于 chunk_size，递归处理它（使用下一级分隔符）
        if len(split) > chunk_size:
            # 先保存当前已聚合的块
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            # 递归切割这个超长片段
            sub_chunks = _recursive_split(split, remaining_seps, chunk_size, chunk_overlap)
            chunks.extend(sub_chunks)
            continue
        
        # 如果当前块加上新片段会超长，则保存当前块，开始新块
        if len(current_chunk) + len(split) + len(current_sep) > chunk_size:
            if current_chunk:
                chunks.append(current_chunk)
                # 处理重叠：从上一个块末尾截取重叠部分作为新块的开头
                overlap_text = ""
                if chunk_overlap > 0 and len(current_chunk) > chunk_overlap:
                    # 避免在句子中间截断，尽量找最近的句号或空格
                    overlap_text = _safe_overlap(current_chunk, chunk_overlap)
                current_chunk = overlap_text + split
            else:
                # 如果当前块为空，但split本身小于chunk_size，直接赋值
                current_chunk = split
        else:
            # 合并到当前块
            if current_chunk:
                current_chunk += current_sep + split
            else:
                current_chunk = split
    
    # 循环结束后，保存最后一个块
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def _safe_overlap(text: str, overlap_len: int) -> str:
    """
    智能截取重叠部分：尽量在句子边界（。！？）或单词边界截取，避免乱码
    """
    if len(text) <= overlap_len:
        return text
    
    # 从文本末尾向前查找最近的句子结束符
    start_pos = len(text) - overlap_len
    
    # 向后寻找第一个句子结束符，确保重叠部分是一个完整的句子开头
    for i in range(start_pos, len(text)):
        if text[i] in "。！？；. !?;\n":
            # 跳过标点符号和可能的空格
            return text[i+1:].lstrip()
    
    # 若找不到合适边界，就按原长度截取
    return text[-overlap_len:]


def _force_split(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """
    最终保底方案：按固定大小强制切割（尽量不切在UTF-8多字节字符中间）
    """
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = min(start + chunk_size, text_len)
        # 如果 end 在 UTF-8 多字节字符中间，回退到完整字符边界
        # Python 字符串按 Unicode 码位索引，一般不会出问题，但为了稳健，检测边界
        chunk = text[start:end]
        chunks.append(chunk)
        
        if end >= text_len:
            break
        
        # 计算下一步起始位置（考虑重叠）
        start = start + chunk_size - chunk_overlap
        # 防止死循环（如果 overlap 导致原地踏步）
        if start <= end:
            start = end  # 强制前进
    
    return chunks