$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.env")) {
  Copy-Item ".\deploy\.env.example" ".\.env" -Force
}

Get-Content ".\.env" | ForEach-Object {
  $line = $_.Trim()
  if ($line.Length -eq 0) { return }
  if ($line.StartsWith("#")) { return }
  $idx = $line.IndexOf("=")
  if ($idx -lt 1) { return }
  $k = $line.Substring(0, $idx).Trim()
  $v = $line.Substring($idx + 1).Trim()
  if ($k.Length -eq 0) { return }
  [System.Environment]::SetEnvironmentVariable($k, $v, "Process")
}

docker compose up -d

$pg = docker compose ps -q postgres
if (-not $pg) { throw "postgres container not found" }

Get-Content ".\deploy\schema.sql" | docker exec -i $pg psql -U $env:POSTGRES_USER -d $env:POSTGRES_DB

$model = $env:OLLAMA_MODEL
if (-not $model) { $model = "qwen2.5:7b" }

docker compose exec -T ollama ollama pull $model
