CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS sys_user (
  id bigserial PRIMARY KEY,
  username varchar(50) NOT NULL,
  useraccount varchar(50) NOT NULL UNIQUE,
  password varchar(100) NOT NULL,
  role varchar(20) NOT NULL DEFAULT 'user',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO sys_user (username, useraccount, password, role)
VALUES ('管理员', 'admin', '123456', 'admin')
ON CONFLICT (useraccount) DO NOTHING;

CREATE TABLE IF NOT EXISTS assistant_config (
  id bigserial PRIMARY KEY,
  key text NOT NULL UNIQUE,
  value text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO assistant_config (key, value)
VALUES
  ('embedding_dim', '768'),
  ('distance_metric', 'cosine'),
  ('chunk_size', '800'),
  ('chunk_overlap', '120')
ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS kb_document (
  id bigserial PRIMARY KEY,
  file_name text NOT NULL,
  file_type text NOT NULL,
  storage_path text NOT NULL,
  status text NOT NULL,
  parse_message text,
  upload_user_id bigint,
  upload_time timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_document_status ON kb_document (status);
CREATE INDEX IF NOT EXISTS idx_kb_document_upload_time ON kb_document (upload_time DESC);

CREATE TABLE IF NOT EXISTS kb_chunk (
  id bigserial PRIMARY KEY,
  document_id bigint NOT NULL REFERENCES kb_document (id) ON DELETE CASCADE,
  chunk_index integer NOT NULL,
  chunk_text text NOT NULL,
  token_count integer,
  embedding vector(1024),
  created_time timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_kb_chunk_doc_idx ON kb_chunk (document_id, chunk_index);

CREATE INDEX IF NOT EXISTS idx_kb_chunk_document_id ON kb_chunk (document_id);

CREATE INDEX IF NOT EXISTS idx_kb_chunk_embedding_hnsw
ON kb_chunk
USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS assistant_session (
  id bigserial PRIMARY KEY,
  user_id bigint NOT NULL,
  session_title text,
  create_time timestamptz NOT NULL DEFAULT now(),
  last_active_time timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_assistant_session_user_id ON assistant_session (user_id, last_active_time DESC);

CREATE TABLE IF NOT EXISTS assistant_message (
  id bigserial PRIMARY KEY,
  session_id bigint NOT NULL REFERENCES assistant_session (id) ON DELETE CASCADE,
  role text NOT NULL,
  content text NOT NULL,
  message_time timestamptz NOT NULL DEFAULT now(),
  answer_status text,
  hit_count integer,
  cost_ms integer
);

CREATE INDEX IF NOT EXISTS idx_assistant_message_session_time ON assistant_message (session_id, message_time);

CREATE TABLE IF NOT EXISTS assistant_message_reference (
  id bigserial PRIMARY KEY,
  message_id bigint NOT NULL REFERENCES assistant_message (id) ON DELETE CASCADE,
  document_id bigint REFERENCES kb_document (id),
  chunk_id bigint REFERENCES kb_chunk (id),
  snippet text
);

CREATE INDEX IF NOT EXISTS idx_assistant_message_reference_message_id ON assistant_message_reference (message_id);

CREATE TABLE IF NOT EXISTS assistant_feedback (
  id bigserial PRIMARY KEY,
  message_id bigint NOT NULL REFERENCES assistant_message (id) ON DELETE CASCADE,
  feedback_type text NOT NULL,
  feedback_note text,
  create_time timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_assistant_feedback_message_id ON assistant_feedback (message_id, create_time DESC);

CREATE TABLE IF NOT EXISTS assistant_audit_log (
  id bigserial PRIMARY KEY,
  user_id bigint,
  action_type text NOT NULL,
  request_summary text,
  response_summary text,
  source_refs jsonb,
  result_flag text,
  create_time timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_assistant_audit_log_user_time ON assistant_audit_log (user_id, create_time DESC);

CREATE TABLE IF NOT EXISTS kb_datasource (
  id bigserial PRIMARY KEY,
  name varchar(100) NOT NULL,
  source_type varchar(20) NOT NULL,
  source_config jsonb NOT NULL,
  sync_frequency varchar(20) NOT NULL DEFAULT 'realtime',
  source_rank integer NOT NULL DEFAULT 5,
  status varchar(20) NOT NULL DEFAULT 'active',
  tenant_id varchar(50),
  is_shared boolean DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE kb_document 
ADD COLUMN IF NOT EXISTS file_hash varchar(64),
ADD COLUMN IF NOT EXISTS file_size bigint,
ADD COLUMN IF NOT EXISTS chunk_count integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS processed_at timestamptz,
ADD COLUMN IF NOT EXISTS datasource_id bigint REFERENCES kb_datasource(id) ON DELETE SET NULL;

ALTER TABLE kb_chunk
ADD COLUMN IF NOT EXISTS datasource_id bigint REFERENCES kb_datasource(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS is_deleted boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS version integer DEFAULT 1;


