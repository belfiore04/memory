#!/bin/bash

cd /Users/jinyijun/Documents/code/memory

echo "🛑 停止周末模式..."

# 停止 PM2 服务
echo "停止 Memory API..."
pm2 stop memory-api 2>/dev/null
pm2 delete memory-api 2>/dev/null

# 停止防休眠
if [ -f .caffeinate.pid ]; then
    echo "停止防休眠..."
    kill $(cat .caffeinate.pid) 2>/dev/null
    rm .caffeinate.pid
fi

# (可选) 停止 Docker - 默认不停止，保持 Qdrant 运行
# echo "停止 Qdrant..."
# docker-compose down

echo ""
echo "✅ 周末模式已停止"
echo "   注意: Qdrant 仍在运行，如需停止请执行: docker-compose down"
