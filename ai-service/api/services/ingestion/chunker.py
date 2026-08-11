"""
文档切块模块
将长文档切分成适合向量化的小块
"""

import re
from typing import List, Tuple


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    separators: List[str] = None
) -> List[Tuple[str, dict]]:
    """
    将文本切分成多个块
    
    Args:
        text: 输入文本
        chunk_size: 每块最大字符数
        chunk_overlap: 块之间的重叠字符数
        separators: 分隔符列表，按优先级排序
    
    Returns:
        List[Tuple[str, dict]]: [(chunk_text, metadata), ...]
    """
    if separators is None:
        separators = ['\n\n', '\n', '。', '！', '？', '；', '. ', '! ', '? ', '; ', ' ']
    
    # 尝试按分隔符切分
    chunks = []
    current_chunk = ""
    current_metadata = {"index": 0}
    
    # 先按段落切分
    paragraphs = re.split(r'\n\s*\n', text)
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # 如果当前块加上新段落超过限制，先保存当前块
        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunks.append((current_chunk, current_metadata.copy()))
            # 保留重叠部分
            overlap_text = current_chunk[-chunk_overlap:] if chunk_overlap > 0 else ""
            current_chunk = overlap_text + para
            current_metadata = {"index": len(chunks)}
        else:
            if current_chunk:
                current_chunk += "\n" + para
            else:
                current_chunk = para
    
    # 保存最后一个块
    if current_chunk:
        chunks.append((current_chunk, current_metadata.copy()))
    
    # 如果切块结果为空或只有一块，按固定大小再切分
    if len(chunks) <= 1:
        chunks = _chunk_by_fixed_size(text, chunk_size, chunk_overlap)
    
    # 为每个块添加元数据
    total = len(chunks)
    for idx, (chunk_text, meta) in enumerate(chunks):
        meta.update({
            "chunk_index": idx,
            "total_chunks": total,
            "char_count": len(chunk_text)
        })
    
    return chunks


def _chunk_by_fixed_size(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50
) -> List[Tuple[str, dict]]:
    """按固定大小切分"""
    chunks = []
    start = 0
    text_len = len(text)
    
    # 防止不合理的 overlap 导致死循环
    if chunk_overlap >= chunk_size:
        chunk_overlap = chunk_size - 1
        
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk_text = text[start:end]
        if chunk_text.strip():
            chunks.append((chunk_text, {"index": len(chunks)}))
            
        # 如果已经切到了文本末尾，直接退出循环，避免死循环
        if end >= text_len:
            break
            
        # 按照步长前进
        start = start + chunk_size - chunk_overlap
    
    return chunks