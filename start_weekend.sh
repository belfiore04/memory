#!/bin/bash

cd /Users/jinyijun/Documents/code/memory

echo "🚀 启动周末无人值守模式..."

# 1. 启动 Docker 服务 (Qdrant)
echo "📦 启动 Qdrant..."
docker-compose up -d

# 2. 等待 Qdrant 就绪
echo "⏳ 等待 Qdrant 就绪..."
sleep 5

# 3. 停止之前可能运行的进程
pm2 delete memory-api 2>/dev/null
pm2 delete ngrok 2>/dev/null
pm2 delete scheduler 2>/dev/null
pkill ngrok 2>/dev/null

# 4. 启动 PM2 管理的所有服务 (memory-api + ngrok)
echo "🔧 启动 Memory API 和 Ngrok (PM2)..."
pm2 start ecosystem.config.js

# 5. 防止 Mac 休眠 (在后台运行)
# 停止之前的 caffeinate
if [ -f .caffeinate.pid ]; then
    kill $(cat .caffeinate.pid) 2>/dev/null
    rm .caffeinate.pid
fi
echo "☕ 启动防休眠..."
caffeinate -d -i -s &
echo $! > .caffeinate.pid

# 6. 显示状态
echo ""
echo "================================"
pm2 status
echo ""
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo "================================"

echo ""
echo "✅ 周末模式已启动！"
echo "   - API: http://localhost:8000"
echo "   - 健康检查: curl http://localhost:8000/health"
echo "   - 查看日志: pm2 logs memory-api"
echo "   - 停止服务: ./stop_weekend.sh"
