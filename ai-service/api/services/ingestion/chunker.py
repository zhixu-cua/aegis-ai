"""
文档切块模块（P0 升级：结构感知 + 父子分块）

按 Markdown 标题层级切分，跟踪标题路径，并为每个块标注：
  - section_title：所在章节标题
  - heading_path：标题层级路径，如 "安装 > 配置 > 数据库"
  - content_type：text / table / code

采用「small-to-big」父子分块：
  - parent_text：完整区块（章节）文本，作为回答时的上下文；
  - children：区块内切分出的子块，作为检索命中单元（精确匹配）。

返回 List[Dict]，每个元素：
  {section_title, heading_path, content_type, parent_text, children}
"""

import re
from typing import List, Dict

_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')
_SENT_SPLIT_RE = re.compile(r'(?<=[。！？!?；;])\s*')


def chunk_text(
    text: str,
    child_size: int = 600,
    child_overlap: int = 80,
    parent_max: int = 2000
) -> List[Dict]:
    """
    结构感知 + 父子分块：
    1. 按标题切分为 section，跟踪 heading_path；
    2. 每个 section 作为一个父块（parent_text），再按句子边界切分为子块（children）。
    """
    if not text or not text.strip():
        return []

    sections = _split_sections(text)

    blocks: List[Dict] = []
    for sec in sections:
        sec_text = sec["text"].strip()
        if not sec_text:
            continue
        content_type = _detect_content_type(sec_text)
        children = _split_section(sec_text, child_size)
        blocks.append({
            "section_title": sec["section_title"],
            "heading_path": sec["heading_path"],
            "content_type": content_type,
            "parent_text": sec_text[:parent_max],
            "children": children,
        })
    return blocks


def _split_sections(text: str) -> List[Dict]:
    """按标题把文本切分为 section，返回 [{heading_path, section_title, text}]"""
    sections: List[Dict] = []
    heading_stack = []  # [(level, title)]
    current = None

    for line in text.split('\n'):
        m = _HEADING_RE.match(line.strip())
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            if current is not None:
                sections.append(current)
            current = {
                "heading_path": " > ".join(t for _, t in heading_stack),
                "section_title": title,
                "text": "",
            }
            continue

        if current is None:
            current = {"heading_path": "", "section_title": "", "text": ""}
        current["text"] += line + "\n"

    if current is not None:
        sections.append(current)

    return [s for s in sections if s["text"].strip()]


def _split_section(text: str, chunk_size: int) -> List[str]:
    """在单个 section 内按句子边界切分，超长句子按 chunk_size 硬切"""
    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    parts = [p for p in _SENT_SPLIT_RE.split(text) if p.strip()]
    chunks: List[str] = []
    cur = ""
    for p in parts:
        if len(p) > chunk_size:
            if cur:
                chunks.append(cur)
                cur = ""
            for i in range(0, len(p), chunk_size):
                chunks.append(p[i:i + chunk_size])
            continue
        if len(cur) + len(p) > chunk_size:
            if cur:
                chunks.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        chunks.append(cur)
    return chunks or [text]


def _detect_content_type(text: str) -> str:
    """识别内容类型：code / table / text"""
    t = text.strip()
    if t.startswith('```') or t.startswith('~~~'):
        return 'code'
    lines = t.split('\n')
    if len(lines) >= 2 and '|' in lines[0] and re.match(r'^\s*\|?[\s:|-]+\|?\s*$', lines[1]):
        return 'table'
    return 'text'
