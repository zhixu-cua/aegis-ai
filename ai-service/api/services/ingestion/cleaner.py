import re

def clean_text(text: str) -> str:
    """
    文档数据清洗管道（在解析后、切块前执行）
    依据清洗流程图：格式清洗 -> 文本规范化 -> 内容去重与过滤 -> 安全与合规
    """
    if not text:
        return text

    # ================= 1. 格式清洗 =================
    # 移除残留的不可见字符、控制字符 (保留换行和制表符)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b-\u200f\u2028-\u202f\ufeff]', '', text)
    
    # 移除常见的页眉页脚特征 (如 "第x页", "- 1 -")
    text = re.sub(r'^\s*(第\s*\d+\s*页|Page\s*\d+|-?\s*\d+\s*-?)\s*$', '', text, flags=re.MULTILINE | re.IGNORECASE)

    # ================= 2. 文本规范化 =================
    # 规范化空白符：将行内连续的空格/制表符替换为单个空格 (避开 Markdown 表格边界，这里做简单替换)
    # 使用后向断言避免破坏 Markdown 表格的 | 前后空格
    text = re.sub(r'(?<!\|)[ \t]{2,}(?!\|)', ' ', text)
    
    # 规范化换行：最多保留两个连续换行符 (段落分隔)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # ================= 3. 内容去重与过滤 =================
    # 段落级连续去重 (避免 OCR 导致的重复行或者文件读取的异常重复)
    lines = text.split('\n')
    dedup_lines = []
    prev_line = None
    for line in lines:
        stripped = line.strip()
        # 忽略空行比对
        if stripped:
            if stripped == prev_line:
                continue
            prev_line = stripped
        dedup_lines.append(line)
    text = '\n'.join(dedup_lines)

    # ================= 4. 特殊内容处理 =================
    # 表格结构化保留、图片/图表文字描述 (在 parser.py 已处理)
    # 代码块格式保留 (上述替换规则已尽量避开破坏性修改)

    # ================= 5. 安全与合规 =================
    # 数据脱敏：手机号码 (11位数字)
    text = re.sub(r'\b(1[3-9]\d)\d{4}(\d{4})\b', r'\1****\2', text)
    
    # 数据脱敏：身份证号码 (18位)
    text = re.sub(r'\b(\d{6})\d{8}(\d{3}[0-9Xx])\b', r'\1********\2', text)
    
    # 数据脱敏：邮箱地址
    text = re.sub(r'\b([a-zA-Z0-9_-]{1,2})[a-zA-Z0-9_-]+(@[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+)+)\b', r'\1***\2', text)

    # 防范 Prompt 注入攻击 (简单关键词过滤/转义)
    injection_patterns = [
        r'(忽略|ignore)\s*(所有|之前|前面|everything|previous)\s*(指令|指示|instructions|prompt)',
        r'你(现在|将要)扮演',
        r'system\s*prompt'
    ]
    for pattern in injection_patterns:
        text = re.sub(pattern, '[已过滤的安全风险内容]', text, flags=re.IGNORECASE)

    return text.strip()
