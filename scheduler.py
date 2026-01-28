"""
定时任务调度器
独立于 HTTP 服务运行
"""
from apscheduler.schedulers.blocking import BlockingScheduler
from jobs.daily_summary_job import run_daily_analysis
import logging
import signal
import sys
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/scheduler.log")
    ]
)
logger = logging.getLogger(__name__)

def shutdown_handler(signum, frame):
    logger.info("收到停止信号，正在停止调度器...")
    sys.exit(0)

if __name__ == "__main__":
    # 注册信号处理
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    scheduler = BlockingScheduler()
    
    # 每天凌晨 3:00 运行
    # scheduler.add_job(run_daily_analysis, 'cron', hour=3, minute=0)
    
    # 测试模式：每 10 分钟运行一次 (方便调试，正式上线改为 daily)
    # scheduler.add_job(run_daily_analysis, 'interval', minutes=10)
    
    # 最终配置: 每天凌晨 03:00
    scheduler.add_job(run_daily_analysis, 'cron', hour=3, minute=0)
    
    logger.info("启动定时任务调度器 (每日 03:00 执行)...")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("调度器已停止")
