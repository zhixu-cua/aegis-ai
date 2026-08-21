@echo off
chcp 65001 >nul
title Aegis AI - Start All
echo ========================================================
echo         正在启动 Aegis AI 智能网站群售后助手
echo ========================================================
echo.

echo [1/6] 正在启动 PostgreSQL 数据库...
:: 启动本地 PostgreSQL 服务
net start postgresql-x64-16 >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] PostgreSQL 可能已经在运行，或服务名称不匹配。
) else (
    echo PostgreSQL 服务已启动。
)
echo.

echo [2/6] 正在启动 Redis 服务...
cd /d "E:\aegis-ai\Redis"
start "Redis-Server" cmd /k "chcp 65001 >nul && redis-server.exe redis.windows.conf"
echo Redis 服务已在独立窗口中启动
echo.

echo [3/6] 正在启动 Ollama 服务...
:: 启动 Ollama，默认会在后台运行
start "" "ollama" serve
echo Ollama 服务启动指令已发送
echo.

echo [4/6] 正在启动 AI 服务 (ai-service)...
cd /d "E:\aegis-ai\ai-service"
start "AI-Service" cmd /k "chcp 65001 >nul && .\venv\Scripts\activate && python main.py"
echo AI 服务已在独立窗口中启动
echo.

echo [5/6] 正在启动 Spring Boot 后端服务 (BackendApplication)...
cd /d "E:\aegis-ai\backend"
start "Backend-Service" cmd /k "chcp 65001 >nul && set JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8 && mvn spring-boot:run"
echo 后端服务已在独立窗口中启动
echo.

echo [6/6] 正在启动 Vue 前端服务 (assistant-web)...
cd /d "E:\aegis-ai\assistant-web"
start "Frontend-Web" cmd /k "chcp 65001 >nul && npm run dev"
echo 前端服务已在独立窗口中启动
echo.

echo ========================================================
echo 所有资源已一键启动完毕！
echo 前端地址通常为: http://localhost:5173
echo 后端地址通常为: http://localhost:8080
echo ========================================================
pause
