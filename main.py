from threading import Thread
from app.utils.logger import get_logger
from app.scheduler import start_scheduler
from app.queue_worker import start_queue_worker

logger = get_logger("main")


def main():
    logger.info("系统启动")

    scheduler_thread = Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()

    queue_thread = Thread(target=start_queue_worker, daemon=False)
    queue_thread.start()

    try:
        queue_thread.join()
    except KeyboardInterrupt:
        logger.info("收到中断信号，停止程序")


if __name__ == "__main__":
    main()
