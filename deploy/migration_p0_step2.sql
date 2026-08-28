-- ============================================================
-- P0 第二步迁移：BM25 倒排索引 + 入库任务状态机（重试/死信）
-- 幂等，可重复执行
-- ============================================================

-- 1) BM25 倒排索引表：term -> (chunk_id, tf)
CREATE TABLE IF NOT EXISTS kb_chunk_terms (
  chunk_id bigint NOT NULL REFERENCES kb_chunk(id) ON DELETE CASCADE,
  term text NOT NULL,
  tf int NOT NULL DEFAULT 1,
  PRIMARY KEY (chunk_id, term)
);
CREATE INDEX IF NOT EXISTS idx_kb_chunk_terms_term ON kb_chunk_terms (term);

-- 2) 入库任务状态机（重试 + 死信记录）
CREATE TABLE IF NOT EXISTS ingest_task (
  id bigserial PRIMARY KEY,
  datasource_id bigint,
  document_id bigint,
  file_path text,
  file_hash text,
  status text NOT NULL DEFAULT 'pending',   -- pending/processing/completed/failed/dead
  attempt int NOT NULL DEFAULT 0,
  max_attempt int NOT NULL DEFAULT 3,
  error_msg text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ingest_task_status ON ingest_task (status);
