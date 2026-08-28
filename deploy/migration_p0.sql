-- ============================================================
-- P0 迁移脚本：kb_chunk 增加结构化分块元数据
-- 幂等，可重复执行；不影响既有数据（新列默认 NULL / 'text'）
-- 向量维度已为 1024（bge-m3），本脚本不涉及向量维度迁移
-- ============================================================

-- 所在章节标题
ALTER TABLE kb_chunk
  ADD COLUMN IF NOT EXISTS section_title text;

-- 标题层级路径，例如 "安装 > 配置 > 数据库"
ALTER TABLE kb_chunk
  ADD COLUMN IF NOT EXISTS heading_path text;

-- 内容类型：text / table / code / parent
ALTER TABLE kb_chunk
  ADD COLUMN IF NOT EXISTS content_type text DEFAULT 'text';

-- 父块 id（small-to-big 预留：child -> parent）
ALTER TABLE kb_chunk
  ADD COLUMN IF NOT EXISTS parent_id bigint REFERENCES kb_chunk(id) ON DELETE SET NULL;

-- 为父子关系与内容类型建索引
CREATE INDEX IF NOT EXISTS idx_kb_chunk_parent_id ON kb_chunk (parent_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunk_content_type ON kb_chunk (content_type);
