@echo off
chcp 65001 >nul
title Aegis AI - Stop All
echo ========================================================
echo         正在停止 Aegis AI 智能网站群售后助手
echo ========================================================
echo.

echo [1/2] 正在关闭本地开发进程 (AI 服务, 后端服务, 前端服务, Redis)...
:: 根据在 start_all.bat 中设置的窗口标题，强制杀死对应的 cmd 窗口及所有的子进程
taskkill /fi "WINDOWTITLE eq AI-Service*" /f /t >nul 2>&1
taskkill /fi "WINDOWTITLE eq Backend-Service*" /f /t >nul 2>&1
taskkill /fi "WINDOWTITLE eq Frontend-Web*" /f /t >nul 2>&1
taskkill /fi "WINDOWTITLE eq Redis-Server*" /f /t >nul 2>&1
echo 所有的本地代码运行窗口及 Redis 已安全关闭。
echo.

echo [2/2] 正在停止本地基础设施服务 (PostgreSQL, Ollama)...
:: 尝试停止 PostgreSQL 服务（注意：如果以普通用户运行可能权限不足，通常保持后台运行也无妨）
net stop postgresql-x64-16 >nul 2>&1
:: 杀死后台的 Ollama 进程
taskkill /im ollama.exe /f >nul 2>&1
echo 本地基础设施进程已尝试关闭。
echo.

echo ========================================================
echo 所有资源已一键安全停止并清理！
echo ========================================================
pause
