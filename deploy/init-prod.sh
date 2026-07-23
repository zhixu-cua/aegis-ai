#!/usr/bin/env bash
set -euo pipefail

if [ ! -f ./.env ]; then
  cp deploy/.env.example ./.env
fi

set -a
. ./.env
set +a

docker compose up -d

pg="$(docker compose ps -q postgres)"
docker exec -i "$pg" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < deploy/schema.sql

model="${OLLAMA_MODEL:-qwen2.5:7b}"
docker compose exec -T ollama ollama pull "$model"
