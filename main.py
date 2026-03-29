from threading import Thread
from app.utils.logger import get_logger
from app.utils.init import reset_stuck_tasks, graceful_shutdown
from app.scheduler import start_scheduler
from app.queue_worker import start_queue_worker

logger = get_logger("main")


def main():
    logger.info("=" * 50)
    logger.info("系统启动")
    logger.info("=" * 50)

    # 启动前重置卡住的任务
    logger.info("检查并重置卡住的任务...")
    reset_stuck_tasks()

    scheduler_thread = Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()

    queue_thread = Thread(target=start_queue_worker, daemon=False)
    queue_thread.start()

    try:
        queue_thread.join()
    except KeyboardInterrupt:
        logger.info("收到中断信号，停止程序")
        graceful_shutdown()


if __name__ == "__main__":
    main()
